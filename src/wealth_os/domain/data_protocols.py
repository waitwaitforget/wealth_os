"""Data OS domain protocols.

Port interfaces that define contracts between domain logic and
infrastructure implementations. All infrastructure adapters must
implement these protocols.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from wealth_os.domain.data_models import (
    CorporateAction,
    DataQualityReport,
    DataVersion,
    FXRate,
    InstrumentMaster,
    Market,
    MarketDataBundle,
    TradingCalendar,
)

# ── Market Data Provider ───────────────────────────────────────────


@runtime_checkable
class MarketDataProvider(Protocol):
    """Fetch raw market data from an external source.

    Implementations should handle network failures, rate limiting,
    and data format conversion internally.
    """

    @property
    def name(self) -> str: ...

    @property
    def markets(self) -> list[Market]: ...

    def fetch_bars(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> pd.DataFrame: ...

    def fetch_dividends(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> list[CorporateAction]: ...

    def fetch_splits(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> list[CorporateAction]: ...


# ── FX Rate Provider ───────────────────────────────────────────────


@runtime_checkable
class FXRateProvider(Protocol):
    """Fetch exchange rates."""

    @property
    def name(self) -> str: ...

    def fetch_rates(
        self,
        pairs: list[str],
        start: date,
        end: date,
    ) -> list[FXRate]: ...


@runtime_checkable
class DataRepository(Protocol):
    """Persistent storage for market data with versioning.

    All writes must be immutable — existing records are never
    silently overwritten.  Read operations return typed domain
    objects or DataFrames.
    """

    def save_bars(self, bars: pd.DataFrame, version: DataVersion) -> None: ...

    def load_bars(
        self,
        instrument_ids: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> pd.DataFrame: ...

    def save_instruments(
        self, instruments: list[InstrumentMaster], version: DataVersion
    ) -> None: ...

    def load_instruments(
        self, instrument_ids: list[str] | None = None, version: DataVersion | None = None
    ) -> list[InstrumentMaster]: ...

    def save_fx_rates(self, rates: list[FXRate], version: DataVersion) -> None: ...

    def load_fx_rates(
        self,
        pairs: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> list[FXRate]: ...

    def save_trading_calendar(self, calendar: TradingCalendar, version: DataVersion) -> None: ...

    def load_trading_calendar(
        self, market: Market, version: DataVersion | None = None
    ) -> TradingCalendar | None: ...

    def load_bundle(
        self,
        instrument_ids: list[str],
        start: date,
        end: date,
        version: DataVersion | None = None,
    ) -> MarketDataBundle: ...

    def list_versions(self) -> list[DataVersion]: ...

    def get_latest_version(self) -> DataVersion | None: ...


# ── Data Quality ───────────────────────────────────────────────────


@runtime_checkable
class DataValidator(Protocol):
    """Validate a MarketDataBundle against data quality rules."""

    def validate(self, bundle: MarketDataBundle) -> DataQualityReport: ...
