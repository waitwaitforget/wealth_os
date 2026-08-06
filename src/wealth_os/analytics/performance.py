from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.optimize import brentq


def drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def time_weighted_return(unit_nav: pd.Series, initial_unit_nav: float | None = 1.0) -> float:
    """Return strategy performance independently of external cash flows.

    The backtest records end-of-day unit NAV.  Passing ``initial_unit_nav=1.0``
    includes first-day deployment costs and first-day PnL in the return.
    Set it to ``None`` when the input series already contains its opening NAV.
    """
    clean = unit_nav.dropna()
    if clean.empty:
        return 0.0
    start = float(initial_unit_nav) if initial_unit_nav is not None else float(clean.iloc[0])
    return float(clean.iloc[-1] / start - 1.0) if start > 0 else float("nan")


def xirr(cash_flows: pd.Series, terminal_value: float, terminal_date: pd.Timestamp) -> float:
    """Calculate investor money-weighted annual return.

    ``cash_flows`` uses the account convention: deposits are positive and
    withdrawals are negative.  They are inverted internally to the investor
    perspective, while terminal value is a positive investor cash flow.
    """
    flows = cash_flows[cash_flows != 0].copy()
    if flows.empty:
        return float("nan")
    signed = -flows.astype(float)
    signed.loc[terminal_date] = signed.get(terminal_date, 0.0) + terminal_value
    t0 = signed.index.min()

    def npv(rate: float) -> float:
        return float(sum(cf / ((1 + rate) ** ((date - t0).days / 365.0)) for date, cf in signed.items()))

    try:
        return float(brentq(npv, -0.9999, 100.0))
    except ValueError:
        return float("nan")


def wealth_summary(
    nav: pd.Series,
    external_cash_flows: pd.Series,
    initial_capital: float,
) -> dict[str, float]:
    """Summarize account wealth without confusing deposits with investment PnL."""
    if nav.empty:
        raise ValueError("nav must not be empty")
    contributions = external_cash_flows.clip(lower=0).sum()
    withdrawals = -external_cash_flows.clip(upper=0).sum()
    net_external_flow = float(external_cash_flows.sum())
    net_invested_capital = float(initial_capital + net_external_flow)
    final_value = float(nav.iloc[-1])
    investment_profit = final_value - net_invested_capital
    simple_return_on_net_invested = (
        investment_profit / net_invested_capital if net_invested_capital > 0 else float("nan")
    )
    return {
        "initial_capital": float(initial_capital),
        "additional_contributions": float(contributions),
        "withdrawals": float(withdrawals),
        "net_invested_capital": net_invested_capital,
        "final_portfolio_value": final_value,
        "investment_profit": float(investment_profit),
        "simple_return_on_net_invested": float(simple_return_on_net_invested),
    }


def performance_summary(
    unit_nav: pd.Series,
    periods_per_year: int = 252,
    initial_unit_nav: float | None = 1.0,
) -> dict[str, float]:
    clean = unit_nav.dropna()
    if clean.empty:
        return {
            "start_date": pd.NaT,
            "end_date": pd.NaT,
            "calendar_days": 0.0,
            "years": 0.0,
            "twr": 0.0,
            "cagr": float("nan"),
            "annualized_return": float("nan"),
            "annualized_volatility": 0.0,
            "downside_volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe": float("nan"),
            "sortino": float("nan"),
            "calmar": float("nan"),
        }

    # Include the opening unit NAV so first-day PnL/costs are not discarded.
    if initial_unit_nav is not None:
        opening_index = clean.index[0] - pd.Timedelta(nanoseconds=1)
        calculation_nav = pd.concat([
            pd.Series([float(initial_unit_nav)], index=[opening_index]),
            clean.astype(float),
        ])
    else:
        calculation_nav = clean.astype(float)

    returns = calculation_nav.pct_change().dropna()
    start_date = pd.Timestamp(clean.index[0])
    end_date = pd.Timestamp(clean.index[-1])
    calendar_days = max((end_date - start_date).days, 0)
    years = calendar_days / 365.2425 if calendar_days > 0 else 0.0
    total = time_weighted_return(clean, initial_unit_nav=initial_unit_nav)
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else float("nan")
    vol = float(returns.std(ddof=0) * math.sqrt(periods_per_year)) if len(returns) else 0.0
    downside = returns[returns < 0]
    downside_vol = float(downside.std(ddof=0) * math.sqrt(periods_per_year)) if len(downside) else 0.0
    dd = drawdown(calculation_nav)
    max_dd = float(dd.min())
    sharpe = float(returns.mean() / returns.std(ddof=0) * math.sqrt(periods_per_year)) if returns.std(ddof=0) > 0 else float("nan")
    sortino = float(returns.mean() * periods_per_year / downside_vol) if downside_vol > 0 else float("nan")
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 and np.isfinite(cagr) else float("nan")
    return {
        "start_date": start_date,
        "end_date": end_date,
        "calendar_days": float(calendar_days),
        "years": float(years),
        "twr": total,
        "cagr": cagr,
        "annualized_return": cagr,
        "annualized_volatility": vol,
        "downside_volatility": downside_vol,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
    }
