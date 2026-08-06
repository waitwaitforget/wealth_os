from __future__ import annotations

import numpy as np
import pandas as pd


def make_synthetic_market(seed: int = 7, periods: int = 1500):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2018-01-01", periods=periods)
    symbols = ["CSI300", "HSI", "SP500", "GOLD", "BOND", "BTC"]
    annual_mu = np.array([0.07, 0.05, 0.09, 0.04, 0.025, 0.15])
    annual_sigma = np.array([0.22, 0.25, 0.18, 0.16, 0.06, 0.65])
    shocks = rng.normal(annual_mu / 252, annual_sigma / np.sqrt(252), size=(periods, len(symbols)))
    prices = pd.DataFrame(100 * np.exp(np.cumsum(shocks, axis=0)), index=index, columns=symbols)

    earnings_yield = pd.DataFrame(
        rng.normal(0.06, 0.015, size=prices.shape), index=index, columns=symbols
    )
    dividend_yield = pd.DataFrame(
        rng.normal(0.025, 0.008, size=prices.shape), index=index, columns=symbols
    )
    # Non-cash-flow assets should not contribute valuation signals.
    earnings_yield[["GOLD", "BTC"]] = np.nan
    dividend_yield[["GOLD", "BTC"]] = np.nan

    contributions = pd.Series(0.0, index=index)
    month_starts = index.to_series().groupby(index.to_period("M")).head(1).index
    contributions.loc[month_starts] = 20_000.0
    contributions.iloc[0] = 0.0
    cash_returns = pd.Series((1.02 ** (1 / 252) - 1), index=index)
    return (
        prices,
        {"earnings_yield": earnings_yield, "dividend_yield": dividend_yield},
        contributions,
        cash_returns,
    )
