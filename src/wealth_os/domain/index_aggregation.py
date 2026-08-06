"""Index valuation aggregation engine.

Implements the index-level metric formulas from the handoff document:

    PE_index = sum(MarketCap_i) / sum(Earnings_i)
    PB_index = sum(MarketCap_i) / sum(BookValue_i)
    DividendYield_index = sum(Dividend_i) / sum(MarketCap_i)
    ROE_index = sum(NetIncome_i) / sum(AverageEquity_i)

All aggregation respects valid_weight tracking and handles
negative-earnings constituents correctly.
"""

from __future__ import annotations

import pandas as pd

from wealth_os.domain.index_valuation import (
    AggregationMethod,
    FundamentalSnapshot,
    IndexConstituent,
    IndexValuationSnapshot,
)


def aggregate_pe(
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
    index_id: str,
    observation_date: pd.Timestamp,
) -> tuple[float | None, float, float]:
    """Aggregate PE = sum(MarketCap) / sum(Earnings_TTM).

    Returns (PE, valid_weight, negative_earnings_weight).
    Returns None if total earnings <= 0 (PE not interpretable).
    """
    total_mcap = 0.0
    total_earnings = 0.0
    valid_mcap = 0.0
    negative_earnings_mcap = 0.0
    total_mcap_all = 0.0

    for c in constituents:
        weight = c.weight or 0.0
        total_mcap_all += weight
        fund = fundamentals.get(c.constituent_id)
        if fund is None or fund.market_cap is None:
            continue
        mcap = fund.market_cap
        total_mcap += mcap
        valid_mcap += weight

        if fund.net_income_ttm is not None:
            total_earnings += fund.net_income_ttm
            if fund.net_income_ttm < 0:
                negative_earnings_mcap += weight

    if total_earnings <= 0 or total_mcap <= 0:
        return (
            None,
            _safe_ratio(valid_mcap, total_mcap_all),
            _safe_ratio(negative_earnings_mcap, total_mcap_all),
        )

    pe = total_mcap / total_earnings
    valid_w = _safe_ratio(valid_mcap, total_mcap_all)
    neg_w = _safe_ratio(negative_earnings_mcap, total_mcap_all)
    return pe, valid_w, neg_w


def aggregate_pb(
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
) -> tuple[float | None, float]:
    """Aggregate PB = sum(MarketCap) / sum(BookValue)."""
    total_mcap = 0.0
    total_book = 0.0

    for c in constituents:
        fund = fundamentals.get(c.constituent_id)
        if fund is None or fund.market_cap is None or fund.book_value is None:
            continue
        total_mcap += fund.market_cap
        total_book += fund.book_value

    if total_book <= 0:
        return None, 0.0

    valid_weight = _safe_ratio(
        sum(
            f.market_cap
            for f in fundamentals.values()
            if f.market_cap is not None and f.book_value is not None
        ),
        sum(f.market_cap or 0 for f in fundamentals.values()),
    )
    return total_mcap / total_book, valid_weight


def aggregate_dividend_yield(
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
) -> float | None:
    """Aggregate DividendYield = sum(Dividend_TTM) / sum(MarketCap)."""
    total_dividend = 0.0
    total_mcap = 0.0

    for c in constituents:
        fund = fundamentals.get(c.constituent_id)
        if fund is None or fund.market_cap is None or fund.dividend_ttm is None:
            continue
        total_dividend += fund.dividend_ttm
        total_mcap += fund.market_cap

    if total_mcap <= 0:
        return None
    return total_dividend / total_mcap


def aggregate_roe(
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
) -> float | None:
    """Aggregate ROE = sum(NetIncome) / sum(AverageEquity)."""
    total_net_income = 0.0
    total_equity = 0.0

    for c in constituents:
        fund = fundamentals.get(c.constituent_id)
        if fund is None or fund.net_income_ttm is None or fund.average_equity is None:
            continue
        total_net_income += fund.net_income_ttm
        total_equity += fund.average_equity

    if total_equity <= 0:
        return None
    return total_net_income / total_equity


def aggregate_ps(
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
) -> float | None:
    """Aggregate PS = sum(MarketCap) / sum(Revenue)."""
    total_mcap = 0.0
    total_revenue = 0.0

    for c in constituents:
        fund = fundamentals.get(c.constituent_id)
        if fund is None or fund.market_cap is None or fund.revenue_ttm is None:
            continue
        total_mcap += fund.market_cap
        total_revenue += fund.revenue_ttm

    if total_revenue <= 0:
        return None
    return total_mcap / total_revenue


def build_snapshot_from_direct(
    index_id: str,
    observation_date: pd.Timestamp,
    pe_ttm: float | None = None,
    pb: float | None = None,
    dividend_yield: float | None = None,
    pe_static: float | None = None,
    ps_ttm: float | None = None,
    roe: float | None = None,
    source: str = "direct",
) -> IndexValuationSnapshot:
    """Build a snapshot from directly-fetched (non-aggregated) data."""
    ey = 1.0 / pe_ttm if (pe_ttm is not None and pe_ttm > 0) else None

    return IndexValuationSnapshot(
        index_id=index_id,
        observation_date=observation_date,
        pe_static=pe_static,
        pe_ttm=pe_ttm,
        pb=pb,
        ps_ttm=ps_ttm,
        dividend_yield=dividend_yield,
        earnings_yield=ey,
        roe=roe,
        aggregation_method=AggregationMethod.DIRECT,
        source=source,
        ingestion_time=pd.Timestamp.now(),
    )


def build_snapshot_from_constituents(
    index_id: str,
    observation_date: pd.Timestamp,
    constituents: list[IndexConstituent],
    fundamentals: dict[str, FundamentalSnapshot],
    source: str = "constituent_aggregation",
) -> IndexValuationSnapshot:
    """Build a valuation snapshot by aggregating from constituents."""
    pe_ttm, valid_weight, neg_weight = aggregate_pe(
        constituents, fundamentals, index_id, observation_date
    )
    pb, _ = aggregate_pb(constituents, fundamentals)
    div_yield = aggregate_dividend_yield(constituents, fundamentals)
    roe = aggregate_roe(constituents, fundamentals)
    ps_ttm = aggregate_ps(constituents, fundamentals)

    ey = 1.0 / pe_ttm if (pe_ttm is not None and pe_ttm > 0) else None

    return IndexValuationSnapshot(
        index_id=index_id,
        observation_date=observation_date,
        pe_ttm=pe_ttm,
        pb=pb,
        ps_ttm=ps_ttm,
        dividend_yield=div_yield,
        earnings_yield=ey,
        roe=roe,
        valid_weight=valid_weight,
        negative_earnings_weight=neg_weight,
        aggregation_method=AggregationMethod.CONSTITUENT_WEIGHTED,
        source=source,
        ingestion_time=pd.Timestamp.now(),
    )


# ── Helpers ──────────────────────────────────────────────────────


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
