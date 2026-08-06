"""Index valuation domain models.

Core data structures for index-level valuation snapshots,
constituent data, aggregation methods, and quality reporting.

All models are immutable and framework-independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd


class ConfidenceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class AggregationMethod(StrEnum):
    """How an index-level metric was derived."""

    DIRECT = "direct"  # fetched from index provider directly
    CONSTITUENT_WEIGHTED = "constituent_weighted"  # aggregated from constituents
    ETF_PROXY = "etf_proxy"  # estimated from ETF data


@dataclass(frozen=True)
class IndexDefinition:
    """Static metadata for a market index."""

    index_id: str
    index_name: str
    provider: str  # e.g. 'CSI', 'HangSeng', 'S&P'
    market: str
    currency: str
    base_date: date | None = None
    launch_date: date | None = None
    methodology_version: str = ""
    rebalance_frequency: str = "semi-annual"
    source_url: str = ""
    created_at: pd.Timestamp | None = None
    updated_at: pd.Timestamp | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Valuation Snapshot ────────────────────────────────────────────


@dataclass(frozen=True)
class IndexValuationSnapshot:
    """Point-in-time valuation for an index on a given date.

    All fields are optional — only populated when data is available.
    ``valid_weight`` tracks the fraction of index market cap for which
    fundamental data was available.
    """

    index_id: str
    observation_date: pd.Timestamp

    # Valuation
    pe_static: float | None = None
    pe_ttm: float | None = None
    pe_forward: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    dividend_yield: float | None = None
    earnings_yield: float | None = None
    equity_risk_premium: float | None = None

    # Fundamentals
    roe: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    net_margin: float | None = None
    operating_margin: float | None = None

    # Structure
    market_cap: float | None = None
    component_count: int | None = None
    valid_component_count: int | None = None
    valid_weight: float | None = None  # 0.0–1.0
    missing_weight: float | None = None
    negative_earnings_weight: float | None = None

    # Metadata
    aggregation_method: AggregationMethod = AggregationMethod.DIRECT
    methodology_version: str = ""
    confidence: ConfidenceTier | None = None
    confidence_score: float | None = None  # 0.0–1.0
    source: str = ""
    source_data_version: str = ""
    effective_time: pd.Timestamp | None = None
    ingestion_time: pd.Timestamp | None = None
    revision: int = 0

    @property
    def pe_valid(self) -> bool:
        return self.pe_ttm is not None and self.pe_ttm > 0 and self.pe_ttm < 1000

    @property
    def has_sufficient_coverage(self) -> bool:
        if self.valid_weight is None:
            return True
        return self.valid_weight >= 0.95


# ── Index Constituent ─────────────────────────────────────────────


@dataclass(frozen=True)
class IndexConstituent:
    """Membership of a security in an index at a point in time."""

    index_id: str
    constituent_id: str  # instrument_id
    announcement_date: date | None = None
    effective_date: date | None = None
    end_date: date | None = None
    weight: float | None = None
    shares: float | None = None
    free_float_factor: float | None = None
    currency: str = ""
    source: str = ""
    ingestion_time: pd.Timestamp | None = None
    revision: int = 0


# ── Fundamental Snapshot ──────────────────────────────────────────


@dataclass(frozen=True)
class FundamentalSnapshot:
    """Point-in-time fundamental data for a single security."""

    instrument_id: str
    report_period: date
    filing_date: date
    effective_date: date | None = None
    currency: str = "CNY"

    market_cap: float | None = None
    revenue_ttm: float | None = None
    net_income_ttm: float | None = None
    book_value: float | None = None
    average_equity: float | None = None
    operating_cash_flow_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    dividend_ttm: float | None = None
    shares_outstanding: float | None = None

    source: str = ""
    source_data_version: str = ""
    revision: int = 0

    @property
    def is_profitable(self) -> bool:
        return self.net_income_ttm is not None and self.net_income_ttm > 0


# ── Quality Report ────────────────────────────────────────────────


@dataclass
class IndexValuationQualityReport:
    """Cross-check calculated index valuation vs official values."""

    index_id: str
    observation_date: pd.Timestamp

    total_component_count: int = 0
    valid_component_count: int = 0
    valid_weight: float = 0.0
    missing_weight: float = 0.0
    negative_earnings_weight: float = 0.0
    stale_financial_weight: float = 0.0
    currency_conversion_missing_weight: float = 0.0

    official_pe: float | None = None
    calculated_pe: float | None = None
    official_pb: float | None = None
    calculated_pb: float | None = None

    severity: str = "INFO"
    issues: list[str] = field(default_factory=list)
    generated_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)

    @property
    def pe_relative_error(self) -> float | None:
        if self.official_pe and self.calculated_pe and self.official_pe > 0:
            return (self.calculated_pe - self.official_pe) / self.official_pe
        return None

    @property
    def pb_relative_error(self) -> float | None:
        if self.official_pb and self.calculated_pb and self.official_pb > 0:
            return (self.calculated_pb - self.official_pb) / self.official_pb
        return None

    def compute_severity(self) -> str:
        has_fail = False
        has_warn = False

        if self.valid_weight < 0.95:
            has_fail = True
            self.issues.append(f"coverage {self.valid_weight:.1%} < 95%")

        pe_err = self.pe_relative_error
        if pe_err is not None:
            if abs(pe_err) > 0.08:
                has_fail = True
                self.issues.append(f"PE error {pe_err:+.2%} > 8%")
            elif abs(pe_err) > 0.03:
                has_warn = True
                self.issues.append(f"PE error {pe_err:+.2%} > 3%")

        pb_err = self.pb_relative_error
        if pb_err is not None:
            if abs(pb_err) > 0.08:
                has_fail = True
                self.issues.append(f"PB error {pb_err:+.2%} > 8%")
            elif abs(pb_err) > 0.03:
                has_warn = True
                self.issues.append(f"PB error {pb_err:+.2%} > 3%")

        if has_fail:
            self.severity = "FAIL"
        elif has_warn:
            self.severity = "WARNING"
        else:
            self.severity = "PASS"
        return self.severity

    def summary(self) -> str:
        lines = [
            f"Index: {self.index_id}",
            f"Date: {self.observation_date.date()}",
            f"Coverage: {self.valid_weight:.1%} (valid), {self.missing_weight:.1%} (missing)",
        ]
        if self.calculated_pe is not None:
            lines.append(f"PE TTM: {self.calculated_pe:.2f}")
        if self.calculated_pb is not None:
            lines.append(f"PB: {self.calculated_pb:.2f}")
        if self.official_pe is not None:
            lines.append(
                f"Official PE: {self.official_pe:.2f}  "
                f"(error: {self.pe_relative_error or 0.0:+.2%})"
            )
        lines.append(f"Severity: {self.severity}")
        if self.issues:
            lines.append("Issues:")
            for i in self.issues:
                lines.append(f"  - {i}")
        return "\n".join(lines)
