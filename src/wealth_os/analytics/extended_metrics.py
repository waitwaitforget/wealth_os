"""Extended risk/return metrics beyond the basic set.

CDaR, Recovery Time, pre-cost return decomposition, currency & cash
contribution estimates.
"""

from __future__ import annotations

import pandas as pd

from wealth_os.analytics.performance import drawdown


def conditional_drawdown_at_risk(drawdowns: pd.Series, confidence: float = 0.95) -> float:
    """CDaR: average of the worst (100-confidence)% drawdowns."""
    dd = drawdowns.dropna()
    if dd.empty:
        return 0.0
    threshold = dd.quantile(1 - confidence)
    return float(dd[dd <= threshold].mean())


def max_drawdown_duration(unit_nav: pd.Series) -> int:
    """Longest consecutive days in drawdown (below previous peak)."""
    dd = drawdown(unit_nav)
    in_dd = dd < -1e-8
    if not in_dd.any():
        return 0

    streaks = in_dd.astype(int).groupby((~in_dd).cumsum()).cumsum()
    return int(streaks.max())


def recovery_time(nav_or_unit_nav: pd.Series) -> int:
    """Maximum number of days to recover from drawdown to new peak."""
    dd = drawdown(nav_or_unit_nav)
    peak_reached = dd >= -1e-8
    if peak_reached.all():
        return 0

    recovery_periods = (peak_reached == False).astype(int)  # noqa: E712
    if not recovery_periods.any():
        return 0
    groups = (peak_reached.diff() == 1).cumsum()
    longest = int(recovery_periods.groupby(groups).sum().max())
    return longest


def pre_cost_metrics(result) -> dict[str, float]:
    """Decompose TWR into pre-cost and post-cost components.

    Returns the percent of TWR lost to transaction costs.
    """
    nav = result.nav.dropna()
    costs = result.transaction_costs

    # Approximate pre-cost NAV
    cum_costs = costs.cumsum()
    pre_cost_nav = nav + cum_costs

    twr_post = float(nav.iloc[-1] / nav.iloc[0] - 1)
    twr_pre = float(pre_cost_nav.iloc[-1] / pre_cost_nav.iloc[0] - 1)
    cost_impact = twr_pre - twr_post

    return {
        "twr_post_cost": twr_post,
        "twr_pre_cost": twr_pre,
        "cost_impact_on_twr": cost_impact,
        "cost_impact_pct": cost_impact / max(abs(twr_pre), 1e-12) * 100,
        "total_costs": float(costs.sum()),
        "avg_annual_cost_bps": (
            float(costs.sum() / max(abs(nav.mean()), 1e-12)) * 10000 / max(results_years(nav), 0.01)
        ),
    }


def currency_contribution_estimate(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    currencies: dict[str, str],
    base_currency: str = "CNY",
) -> dict[str, object]:
    """Estimate currency impact from asset currency labels."""
    if prices.empty or weights.empty:
        return {}

    by_currency: dict[str, float] = {}
    for sym, cur in currencies.items():
        if sym in prices.columns and sym in weights.columns:
            avg_w = float(weights[sym].mean())
            ret = float(prices[sym].iloc[-1] / prices[sym].iloc[0] - 1)
            by_currency[cur] = by_currency.get(cur, 0.0) + avg_w * ret

    return {"currency_contribution": by_currency}


def cash_contribution(
    nav: pd.Series,
    cash_series: pd.Series,
    cash_yield_annual: float = 0.02,
) -> dict[str, float]:
    """Estimate how much of TWR came from cash yield vs risky assets."""
    twr = float(nav.iloc[-1] / nav.iloc[0] - 1) if len(nav) > 1 else 0.0
    avg_cash_ratio = float(cash_series.mean() / nav.mean())
    years = results_years(nav)

    cash_twr = (1 + cash_yield_annual) ** years - 1
    cash_contribution_val = cash_twr * avg_cash_ratio
    risky_contribution = twr - cash_contribution_val

    return {
        "avg_cash_ratio": avg_cash_ratio,
        "cash_twr": cash_twr,
        "cash_contribution_to_twr": cash_contribution_val,
        "risky_contribution_to_twr": risky_contribution,
    }


def extended_metrics(
    result,
    prices: pd.DataFrame | None = None,
    currencies: dict[str, str] | None = None,
) -> dict[str, float]:
    """Comprehensive metrics including CDaR, recovery, cost breakdown."""
    perf = {}
    unit = result.unit_nav.dropna()
    dd_series = drawdown(unit)

    perf["cdar_95"] = conditional_drawdown_at_risk(dd_series, confidence=0.95)
    perf["cdar_99"] = conditional_drawdown_at_risk(dd_series, confidence=0.99)
    perf["max_dd_duration_days"] = float(max_drawdown_duration(unit))
    perf["recovery_time_days"] = float(recovery_time(unit))

    cost = pre_cost_metrics(result)
    perf.update(cost)

    perf["total_turnover"] = float(result.turnover.sum()) * 2  # one-way = half of two-way

    cash = cash_contribution(result.nav, result.cash)
    perf.update(cash)

    return perf


def results_years(series: pd.Series) -> float:
    return max(float((series.index[-1] - series.index[0]).total_seconds() / 86400.0), 0) / 365.2425


def full_performance_report(
    result,
    prices: pd.DataFrame | None = None,
    currencies: dict[str, str] | None = None,
    label: str = "",
) -> str:
    """Human-readable performance report with all metrics."""
    from wealth_os.analytics.performance import performance_summary

    base = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    ext = extended_metrics(result, prices, currencies)

    lines = []
    if label:
        lines.append(f"\n{'=' * 60}")
        lines.append(f"  {label}")
        lines.append(f"{'=' * 60}")
    lines.append(
        f"  Period: {pd.Timestamp(base['start_date']).date()} → "
        f"{pd.Timestamp(base['end_date']).date()} ({base['years']:.2f} years)"
    )
    lines.append(f"  TWR (post-cost):         {base['twr']:>10.2%}")
    lines.append(f"  TWR (pre-cost):          {ext['twr_pre_cost']:>10.2%}")
    lines.append(f"  Cost impact on TWR:      {ext['cost_impact_on_twr']:>10.2%}")
    lines.append(f"  CAGR:                    {base['annualized_return']:>10.2%}")
    lines.append(f"  Volatility:              {base['annualized_volatility']:>10.2%}")
    lines.append(f"  Max Drawdown:            {base['max_drawdown']:>10.2%}")
    lines.append(f"  CDaR (95%):              {ext['cdar_95']:>10.2%}")
    lines.append(f"  Recovery Time (days):    {ext['recovery_time_days']:>10.0f}")
    lines.append(f"  Sharpe Ratio:            {base['sharpe']:>10.3f}")
    lines.append(f"  Sortino Ratio:           {base['sortino']:>10.3f}")
    lines.append(f"  Calmar Ratio:            {base['calmar']:>10.3f}")
    lines.append(f"  Total Turnover:          {ext['total_turnover']:>10.0%}")
    lines.append(f"  Avg Annual Cost (bps):   {ext['avg_annual_cost_bps']:>10.1f}")
    lines.append(f"  Cash Contr. to TWR:      {ext['cash_contribution_to_twr']:>10.2%}")
    lines.append(f"  Risky Contr. to TWR:     {ext['risky_contribution_to_twr']:>10.2%}")
    lines.append(
        f"  Orders:                  {len(result.orders) if result.orders is not None else 0:>10d}"
    )
    return "\n".join(lines)
