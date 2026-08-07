"""Strategic Asset Allocation — the baseline benchmark strategy."""

from __future__ import annotations

import pandas as pd


def static_saa_weights(
    symbols: list[str],
    weights: dict[str, float] | None = None,
) -> pd.Series:
    if weights:
        return pd.Series(weights).reindex(symbols).fillna(0.0)
    n = len(symbols)
    return pd.Series(1.0 / n, index=symbols)


def risk_managed_core_weights(
    base_weights: pd.Series,
    volatility: float,
    target_vol: float = 0.10,
    max_cash: float = 0.50,
) -> pd.Series:
    """Risk Managed Core: SAA × volatility scaling."""
    if volatility <= 0:
        return base_weights

    scale = min(1.0, target_vol / volatility)
    risky = base_weights.drop("CASH_CNY", errors="ignore")
    scaled = risky * scale

    cash_w = 1.0 - scaled.sum()
    cash_w = min(cash_w, max_cash)
    result = scaled * (1.0 - cash_w) / max(scaled.sum(), 1e-12)
    result["CASH_CNY"] = cash_w
    return result


def adaptive_core_tilt(
    base_weights: pd.Series,
    value_scores: pd.Series,
    alpha_v: float = 0.15,
) -> pd.Series:
    """Adaptive Core: SAA × (1 + alpha_v * value_score).

    Value tilt is deliberately constrained to ±alpha_v of base weight.
    """
    tilted = base_weights * (1.0 + alpha_v * value_scores.fillna(0.0).clip(-1, 1))
    tilted = tilted.clip(lower=0)
    tilted["CASH_CNY"] = 1.0 - tilted.drop("CASH_CNY", errors="ignore").sum()
    return tilted
