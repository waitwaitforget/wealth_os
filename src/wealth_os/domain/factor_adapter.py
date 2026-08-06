"""Index valuation factor adapter.

Bridge between the index valuation domain models and the factor
system.  Converts IndexValuationSnapshot objects into factor
inputs (earnings_yield, dividend_yield DataFrames).
"""

from __future__ import annotations

import pandas as pd

from wealth_os.domain.index_valuation import IndexValuationSnapshot


def snapshots_to_factor_inputs(
    snapshots: list[IndexValuationSnapshot],
    symbols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Convert a list of snapshots into factor-compatible DataFrames.

    Returns:
        {
            "earnings_yield": DataFrame (date × symbol),
            "dividend_yield": DataFrame (date × symbol),
            "pb": DataFrame (date × symbol),
        }
    """
    earnings: dict[pd.Timestamp, dict[str, float]] = {}
    dividends: dict[pd.Timestamp, dict[str, float]] = {}
    pb: dict[pd.Timestamp, dict[str, float]] = {}

    for snap in snapshots:
        idx = snap.index_id
        if symbols is not None and idx not in symbols:
            continue
        ts = snap.observation_date

        if snap.earnings_yield is not None:
            earnings.setdefault(ts, {})[idx] = snap.earnings_yield
        if snap.dividend_yield is not None:
            dividends.setdefault(ts, {})[idx] = snap.dividend_yield
        if snap.pb is not None:
            pb.setdefault(ts, {})[idx] = snap.pb

    return {
        "earnings_yield": pd.DataFrame.from_dict(earnings, orient="index").sort_index(),
        "dividend_yield": pd.DataFrame.from_dict(dividends, orient="index").sort_index(),
        "pb": pd.DataFrame.from_dict(pb, orient="index").sort_index(),
    }


def snapshot_to_dict(snapshot: IndexValuationSnapshot) -> dict:
    """Serialize a snapshot for display."""
    return {
        "index": snapshot.index_id,
        "date": str(snapshot.observation_date.date()),
        "pe_ttm": snapshot.pe_ttm,
        "pb": snapshot.pb,
        "dividend_yield": snapshot.dividend_yield,
        "earnings_yield": snapshot.earnings_yield,
        "roe": snapshot.roe,
        "valid_weight": snapshot.valid_weight,
        "negative_earnings_weight": snapshot.negative_earnings_weight,
        "source": snapshot.source,
    }
