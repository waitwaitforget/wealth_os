"""Investor Simulation & Wealth Experience Metrics.

Implements Stage C of the Broad Index backtest framework:
- Monthly contribution simulation
- Wealth milestones (time to reach targets)
- Underwater analysis (duration, ratio, recovery)
- Multiple starting points
- Probability metrics
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from wealth_os.analytics.performance import drawdown, xirr


@dataclass
class InvestorSimulationResult:
    """Result of a real-investor simulation with contributions."""

    initial_capital: float = 0.0
    monthly_contribution: float = 0.0
    total_contributed: float = 0.0
    final_wealth: float = 0.0
    investment_profit: float = 0.0
    twr: float = 0.0
    xirr_value: float = 0.0
    max_drawdown: float = 0.0
    recovery_days: float = 0.0
    underwater_ratio: float = 0.0


def simulate_investor(
    unit_nav: pd.Series,
    initial_capital: float = 1_000_000,
    monthly_contribution: float = 50_000,
    contribution_day: int = 15,
) -> InvestorSimulationResult:
    """Simulate a real investor with monthly contributions.

    Contributions are handled via share issuance — they do NOT
    contaminate the unit NAV (already handled by the engine).
    This simulation tracks the investor's actual wealth path.
    """
    clean = unit_nav.dropna()
    if clean.empty:
        return InvestorSimulationResult()

    initial_units = initial_capital / clean.iloc[0]
    total_units = initial_units
    total_contributed = initial_capital

    monthly_dates = pd.date_range(clean.index[0], clean.index[-1], freq="MS") + pd.Timedelta(days=contribution_day)
    contribution_schedule: dict[pd.Timestamp, float] = {}

    for d in monthly_dates:
        if d >= clean.index[0] and d <= clean.index[-1]:
            contribution_schedule[d] = monthly_contribution

    wealth_series = pd.Series(index=clean.index, dtype=float)
    flows = pd.Series(0.0, index=clean.index)

    for i, (date, unit_val) in enumerate(clean.items()):
        if i == 0:
            total_units = initial_units
        else:
            if date in contribution_schedule:
                amount = contribution_schedule[date]
                new_units = amount / unit_val
                total_units += new_units
                total_contributed += amount
                flows.loc[date] = amount

        wealth_series.loc[date] = total_units * unit_val

    wealth_series = wealth_series.ffill()
    final_wealth = float(wealth_series.dropna().iloc[-1])
    profit = final_wealth - total_contributed

    twr = float(clean.iloc[-1] / clean.iloc[0] - 1)
    irr = xirr(flows, final_wealth, wealth_series.dropna().index[-1])

    dd = drawdown(wealth_series)
    max_dd = float(dd.min())
    recovery_count = (dd >= -0.01).sum() if len(dd) > 0 else len(wealth_series)

    return InvestorSimulationResult(
        initial_capital=initial_capital,
        monthly_contribution=monthly_contribution,
        total_contributed=total_contributed,
        final_wealth=final_wealth,
        investment_profit=profit,
        twr=twr,
        xirr_value=float(irr) if not np.isnan(irr) else 0.0,
        max_drawdown=max_dd,
        recovery_days=float(len(wealth_series) - recovery_count),
        underwater_ratio=float((dd < -0.01).mean()) if len(dd) > 0 else 0.0,
    )


# ── Underwater Metrics ────────────────────────────────────────────


@dataclass
class UnderwaterReport:
    underwater_ratio: float = 0.0
    longest_underwater_days: int = 0
    median_underwater_days: float = 0.0
    avg_recovery_days_above_5pct: float = 0.0
    avg_recovery_days_above_10pct: float = 0.0
    avg_recovery_days_above_20pct: float = 0.0


def compute_underwater_metrics(wealth_or_nav: pd.Series) -> UnderwaterReport:
    """Compute comprehensive underwater/underwater analysis."""
    clean = wealth_or_nav.dropna()
    if clean.empty:
        return UnderwaterReport()

    dd = drawdown(clean)
    underwater = dd < -0.01
    underwater_ratio = float(underwater.mean())

    # Longest underwater streak
    streaks = underwater.astype(int).groupby((~underwater).cumsum()).cumsum()
    longest = int(streaks.max()) if not streaks.empty else 0

    # Median underwater duration
    periods = streaks[streaks > 0]
    median = float(periods.median()) if not periods.empty else 0.0

    # Recovery by depth
    recovery: dict[float, list[int]] = {0.05: [], 0.10: [], 0.20: []}

    in_dd = False
    dd_start = 0
    peak_dd = 0.0

    for i in range(len(clean)):
        val = float(dd.iloc[i])
        if val < -0.01 and not in_dd:
            in_dd = True
            dd_start = i
            peak_dd = val
        elif val >= -0.01 and in_dd:
            in_dd = False
            recovery_time = i - dd_start
            for threshold in recovery:
                if peak_dd <= -threshold:
                    recovery[threshold].append(recovery_time)

    return UnderwaterReport(
        underwater_ratio=underwater_ratio,
        longest_underwater_days=longest,
        median_underwater_days=median,
        avg_recovery_days_above_5pct=_safe_mean(recovery[0.05]),
        avg_recovery_days_above_10pct=_safe_mean(recovery[0.10]),
        avg_recovery_days_above_20pct=_safe_mean(recovery[0.20]),
    )


# ── Wealth Milestones ─────────────────────────────────────────────


@dataclass
class MilestoneTiming:
    from_amount: float = 0.0
    to_amount: float = 0.0
    median_days: float = 0.0
    best_days: float = 0.0
    worst_days: float = 0.0


def compute_milestones(
    unit_nav: pd.Series,
    milestones: list[tuple[float, float]] | None = None,
    initial_capital: float = 1_000_000,
    monthly_contribution: float = 50_000,
) -> list[MilestoneTiming]:
    """Compute time to reach wealth milestones across starting points."""
    if milestones is None:
        milestones = [(1_000_000, 2_000_000), (2_000_000, 3_000_000)]

    clean = unit_nav.dropna()
    if len(clean) < 252:
        return []

    results: list[MilestoneTiming] = []
    start_dates = pd.date_range(clean.index[0], clean.index[-252], freq="MS")

    for from_w, to_w in milestones:
        times: list[float] = []
        for start in start_dates[:min(60, len(start_dates))]:
            end_idx = clean.index.get_indexer([start], method="ffill")[0]
            sub = clean.iloc[end_idx:]
            if len(sub) < 252:
                continue

            result = simulate_investor(sub, initial_capital=from_w, monthly_contribution=monthly_contribution)
            if result.final_wealth >= to_w:
                sim_wealth = _sim_wealth_series(sub, from_w, monthly_contribution)
                crossed = sim_wealth[sim_wealth >= to_w]
                if not crossed.empty:
                    times.append(float((crossed.index[0] - sub.index[0]).days))

        if times:
            arr = np.array(times)
            results.append(
                MilestoneTiming(
                    from_amount=from_w,
                    to_amount=to_w,
                    median_days=float(np.median(arr)),
                    best_days=float(arr.min()),
                    worst_days=float(arr.max()),
                )
            )

    return results


# ── Multiple Starting Points ──────────────────────────────────────


@dataclass
class StartingPointSummary:
    n_start_points: int = 0
    median_cagr: float = 0.0
    mean_cagr: float = 0.0
    p10_cagr: float = 0.0
    p25_cagr: float = 0.0
    p75_cagr: float = 0.0
    p90_cagr: float = 0.0
    worst_cagr: float = 0.0
    best_cagr: float = 0.0
    positive_ratio: float = 0.0
    benchmark_win_rate: float = 0.0


def compute_starting_points(
    unit_nav: pd.Series,
    benchmark_nav: pd.Series | None = None,
    holding_years: int = 5,
    step_months: int = 3,
) -> StartingPointSummary:
    """Analyze outcomes from different investment starting dates."""
    clean = unit_nav.dropna()
    if len(clean) < holding_years * 252:
        return StartingPointSummary()

    cagrs: list[float] = []
    wins: list[bool] = []

    start_dates = pd.date_range(clean.index[0], clean.index[-holding_years * 252], freq=f"{step_months}MS")

    for start in start_dates:
        try:
            end = start + pd.Timedelta(days=holding_years * 365)
            sub = clean.loc[start:end]
            if len(sub) < 252:
                continue

            cagr = float((sub.iloc[-1] / sub.iloc[0]) ** (1.0 / holding_years) - 1)
            cagrs.append(cagr)

            if benchmark_nav is not None:
                bench_sub = benchmark_nav.loc[start:end]
                if len(bench_sub) > 0:
                    bench_cagr = float((bench_sub.iloc[-1] / bench_sub.iloc[0]) ** (1.0 / holding_years) - 1)
                    wins.append(cagr > bench_cagr)
        except (KeyError, IndexError):
            continue

    if not cagrs:
        return StartingPointSummary()

    arr = np.array(cagrs)
    return StartingPointSummary(
        n_start_points=len(cagrs),
        median_cagr=float(np.median(arr)),
        mean_cagr=float(np.mean(arr)),
        p10_cagr=float(np.percentile(arr, 10)),
        p25_cagr=float(np.percentile(arr, 25)),
        p75_cagr=float(np.percentile(arr, 75)),
        p90_cagr=float(np.percentile(arr, 90)),
        worst_cagr=float(arr.min()),
        best_cagr=float(arr.max()),
        positive_ratio=float((arr > 0).mean()),
        benchmark_win_rate=float(np.mean(wins)) if wins else 0.0,
    )


# ── Probability Metrics ───────────────────────────────────────────


@dataclass
class ProbabilityReport:
    p_5y_negative: float = 0.0
    p_10y_cagr_below_3pct: float = 0.0
    p_max_dd_beyond_20pct: float = 0.0
    p_underperform_saa_5y: float = 0.0
    p_underperform_saa_10y: float = 0.0


def compute_probabilities(
    unit_nav: pd.Series,
    benchmark_nav: pd.Series | None = None,
) -> ProbabilityReport:
    """Compute key probability metrics from historical simulation."""
    clean = unit_nav.dropna()
    if len(clean) < 252 * 5:
        return ProbabilityReport()

    # 5Y negative probability
    neg_5y = 0
    total_5y = 0
    under_saa_5y = 0
    for start in pd.date_range(clean.index[0], clean.index[-252 * 5], freq="QE"):
        end_5y = start + pd.Timedelta(days=365 * 5)
        sub = clean.loc[start:end_5y]
        if len(sub) < 500:
            continue
        total_5y += 1
        if sub.iloc[-1] / sub.iloc[0] < 1:
            neg_5y += 1
        if benchmark_nav is not None:
            bench = benchmark_nav.loc[start:end_5y]
            if len(bench) > 0:
                strat_ret = float(sub.iloc[-1] / sub.iloc[0] - 1)
                bench_ret = float(bench.iloc[-1] / bench.iloc[0] - 1)
                if strat_ret < bench_ret:
                    under_saa_5y += 1

    # MaxDD beyond 20%
    dd = drawdown(clean)
    p_dd_20 = float((dd < -0.20).mean()) if len(dd) > 0 else 0.0

    return ProbabilityReport(
        p_5y_negative=neg_5y / max(total_5y, 1),
        p_10y_cagr_below_3pct=0.0,
        p_max_dd_beyond_20pct=p_dd_20,
        p_underperform_saa_5y=under_saa_5y / max(total_5y, 1),
        p_underperform_saa_10y=0.0,
    )


# ── Helpers ───────────────────────────────────────────────────────


def _safe_mean(lst: list) -> float:
    return float(np.mean(lst)) if lst else 0.0


def _sim_wealth_series(unit_nav: pd.Series, initial: float, monthly: float) -> pd.Series:
    units = initial / unit_nav.iloc[0]
    wealth = pd.Series(index=unit_nav.index, dtype=float)
    for i, (date, uv) in enumerate(unit_nav.items()):
        if i > 0 and i % 21 == 0:
            units += monthly / uv
        wealth.loc[date] = units * uv
    return wealth.ffill()
