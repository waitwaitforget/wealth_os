from __future__ import annotations

import pandas as pd


def drawdown_risk_multiplier(drawdown: float) -> float:
    if drawdown <= -0.20:
        return 0.30
    if drawdown <= -0.15:
        return 0.50
    if drawdown <= -0.10:
        return 0.70
    if drawdown <= -0.05:
        return 0.85
    return 1.0


def apply_drawdown_overlay(weights: pd.Series, cash_symbol: str, drawdown: float) -> pd.Series:
    out = weights.copy()
    multiplier = drawdown_risk_multiplier(drawdown)
    risky = out.drop(cash_symbol, errors="ignore") * multiplier
    out.loc[risky.index] = risky
    out.loc[cash_symbol] = 1.0 - risky.sum()
    return out
