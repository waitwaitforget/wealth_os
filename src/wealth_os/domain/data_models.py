"""Data OS domain models.

Core data structures for the canonical data model, including
instruments, market bars, FX rates, trading calendars, data
versioning, and quality reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd

from wealth_os.domain.models import AssetClass


class Market(StrEnum):
    """Trading market identifier."""

    SSE = "SSE"  # 上海证券交易所
    SZSE = "SZSE"  # 深圳证券交易所
    HKEX = "HKEX"  # 香港交易所
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    CRYPTO = "CRYPTO"
    FX = "FX"


class InstrumentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELISTED = "delisted"


class DataQuality(StrEnum):
    CLEAN = "clean"
    SUSPECT = "suspect"
    MISSING = "missing"
    STALE = "stale"
    QUARANTINE = "quarantine"


# ── Instrument Master ──────────────────────────────────────────────


@dataclass(frozen=True)
class InstrumentMaster:
    """Canonical instrument master record.

    All business logic references instruments by their stable
    ``instrument_id``. Vendor-level tickers are mapped through
    ``vendor_symbols`` and never used as permanent primary keys.
    """

    instrument_id: str
    symbol: str
    name: str
    asset_class: AssetClass
    market: Market
    currency: str
    vendor_symbols: dict[str, str] = field(default_factory=dict)
    exchange: str = ""
    trading_calendar: str = ""
    lot_size: int = 1
    price_multiplier: float = 1.0
    start_date: date | None = None
    end_date: date | None = None
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == InstrumentStatus.ACTIVE


# ── Market Bar ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Bar:
    """Single OHLCV market bar with quality metadata."""

    instrument_id: str
    event_time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: float = 0.0
    currency: str = ""
    source: str = ""
    revision: int = 0
    quality: DataQuality = DataQuality.CLEAN
    ingested_at: pd.Timestamp | None = None

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("OHLC prices must be positive")

    @property
    def is_suspect(self) -> bool:
        return self.quality != DataQuality.CLEAN


# ── Corporate Action ───────────────────────────────────────────────


class CorporateActionType(StrEnum):
    DIVIDEND = "dividend"
    SPLIT = "split"
    MERGER = "merger"
    DELISTING = "delisting"


@dataclass(frozen=True)
class CorporateAction:
    instrument_id: str
    action_type: CorporateActionType
    effective_time: pd.Timestamp
    announced_at: pd.Timestamp | None = None
    amount: float = 0.0  # dividend per share or split ratio
    currency: str = ""
    description: str = ""


# ── FX Rate ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FXRate:
    """Exchange rate from base_currency to quote_currency.

    A rate of 7.25 for USD/CNY means 1 USD = 7.25 CNY.
    """

    base_currency: str
    quote_currency: str
    event_time: pd.Timestamp
    rate: float
    source: str = ""
    quality: DataQuality = DataQuality.CLEAN

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("FX rate must be positive")

    @property
    def pair(self) -> str:
        return f"{self.base_currency}/{self.quote_currency}"

    def invert(self) -> FXRate:
        return FXRate(
            base_currency=self.quote_currency,
            quote_currency=self.base_currency,
            event_time=self.event_time,
            rate=1.0 / self.rate,
            source=self.source,
            quality=self.quality,
        )


# ── Trading Calendar ───────────────────────────────────────────────


@dataclass(frozen=True)
class TradingCalendar:
    """Market-specific trading day collection."""

    market: Market
    trading_days: frozenset[date]
    early_close_dates: dict[date, str] = field(default_factory=dict)
    holidays: frozenset[date] = field(default_factory=frozenset)
    timezone: str = "UTC"

    def is_trading_day(self, d: date) -> bool:
        return d in self.trading_days

    def next_trading_day(self, d: date, n: int = 1) -> date:
        sorted_days = sorted(self.trading_days)
        idx = _bisect_right(sorted_days, d)
        if n > 0:
            return sorted_days[min(idx + n - 1, len(sorted_days) - 1)]
        return sorted_days[max(idx + n, 0)]

    def trading_days_between(self, start: date, end: date) -> list[date]:
        return [d for d in sorted(self.trading_days) if start <= d <= end]


def _bisect_right(a: list[date], x: date) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


# ── Data Version ───────────────────────────────────────────────────


@dataclass(frozen=True)
class DataVersion:
    """Immutable reference to a specific data snapshot."""

    version_id: str
    created_at: pd.Timestamp
    instruments_hash: str = ""
    bars_hash: str = ""
    fx_hash: str = ""
    calendar_hash: str = ""
    source_files: list[str] = field(default_factory=list)
    transform_version: str = "0.1.0"
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def composite_hash(self) -> str:
        import hashlib

        parts = [
            self.instruments_hash,
            self.bars_hash,
            self.fx_hash,
            self.calendar_hash,
            self.transform_version,
            str(sorted(self.parameters.items())),
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ── Data Bundle ────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketDataBundle:
    """A point-in-time data snapshot for a given date range."""

    prices: pd.DataFrame  # columns = instruments, index = timestamp
    fx_rates: dict[str, pd.Series] = field(default_factory=dict)
    volumes: pd.DataFrame | None = None
    adjusted_closes: pd.DataFrame | None = None
    data_version: DataVersion | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.prices.index.is_monotonic_increasing:
            raise ValueError("Price index must be monotonic increasing")


# ── Data Quality Report ────────────────────────────────────────────


class DataQualitySeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class DataQualityIssue:
    severity: DataQualitySeverity
    code: str
    message: str
    instrument_id: str = ""
    timestamp: pd.Timestamp | None = None


@dataclass
class DataQualityReport:
    report_id: str = ""
    generated_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    data_version: DataVersion | None = None
    issues: list[DataQualityIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DataQualitySeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DataQualitySeverity.WARNING)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def summary(self) -> str:
        total = len(self.issues)
        if total == 0:
            return "DATA HEALTH: PASS (no issues)"
        status = "FAIL" if self.error_count > 0 else "PASS_WITH_WARNINGS"
        return (
            f"DATA HEALTH: {status}\n"
            f"  Errors: {self.error_count}, Warnings: {self.warning_count}, "
            f"Info: {total - self.error_count - self.warning_count}\n"
            + "\n".join(f"  [{i.severity}] {i.code}: {i.message}" for i in self.issues)
        )
