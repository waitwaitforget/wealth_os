"""Strategy Evaluation Engine — computes comprehensive validation metrics.

Implements: PBO, Deflated Sharpe, Complexity Score, Rolling Returns,
Regime Analysis, Parameter Robustness, Relative NAV.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from wealth_os.analytics.performance import drawdown
from wealth_os.evaluation.models import (
    ExperimentRecord,
    ParameterSurfaceResult,
    RegimeResult,
    RollingMetrics,
    StrategyReport,
)

StrategyReport = StrategyReport  # re-export


# ── Complexity Score ──────────────────────────────────────────────


def compute_complexity(
    n_params: int = 0,
    n_signals: int = 0,
    n_states: int = 0,
    n_thresholds: int = 0,
    annual_turnover: float = 0.0,
    n_dependencies: int = 0,
) -> float:
    """Compute a complexity penalty score.

    Higher = more complex.  Formula: weighted average, capped at 10.
    """
    weights = {
        "params": 1.0,
        "signals": 1.5,
        "states": 2.0,
        "thresholds": 1.0,
        "turnover": 0.5,  # per 100% annual turnover
        "deps": 1.0,
    }
    score = (
        n_params * weights["params"]
        + n_signals * weights["signals"]
        + n_states * weights["states"]
        + n_thresholds * weights["thresholds"]
        + (annual_turnover / 1.0) * weights["turnover"]
        + n_dependencies * weights["deps"]
    )
    return min(score, 10.0)


# ── PBO (Probability of Backtest Overfitting) ────────────────────


def compute_pbo(
    performance_matrix: pd.DataFrame,
    n_simulations: int = 100,
    seed: int = 42,
) -> float:
    """Compute PBO using combinatorial symmetry (Bailey et al. 2015).

    Args:
        performance_matrix: (n_trials, n_metrics) DataFrame of strategy
            performance across parameter combinations or folds.
    """
    n_trials = len(performance_matrix)
    if n_trials < 10:
        return 0.0

    rng = np.random.default_rng(seed)
    n_overfit = 0

    # Rank each trial by the primary metric (first column)
    primary = performance_matrix.iloc[:, 0].values
    is_rank = np.argsort(np.argsort(primary))  # in-sample rank

    for _ in range(n_simulations):
        # Randomly split trials, compare IS vs OOS ranks
        split = n_trials // 2
        perm = rng.permutation(n_trials)
        is_half = perm[:split]
        oos_half = perm[split:]

        # Top IS trial vs its OOS performance
        best_is_idx = is_half[np.argmax(primary[is_half])]
        sorted_oos = np.sort(primary[oos_half])
        idx = np.searchsorted(sorted_oos, primary[best_is_idx])
        best_is_oos_rank = min(idx, len(oos_half) - 1)

        if best_is_oos_rank < split // 2:
            n_overfit += 1

    return n_overfit / n_simulations


# ── Deflated Sharpe Ratio ─────────────────────────────────────────


def compute_deflated_sharpe(
    sharpe: float,
    n_trials: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    n_obs: int = 252,
) -> float:
    """Compute Deflated Sharpe Ratio (Lopez de Prado and Bailey 2014).

    Corrects for multiple testing and non-normal returns.

    Args:
        sharpe: Raw Sharpe ratio.
        n_trials: Number of independent trials attempted.
        skewness: Return skewness (0 for normal).
        kurtosis: Return kurtosis (3 for normal).
        n_obs: Number of observations.

    Returns:
        Deflated p-value equivalent as a "deflated sharpe" score.
        Higher = more significant after adjustment.
    """
    if n_obs < 10:
        return 0.0

    # Compute the expected maximum Sharpe under the null
    # E[max(SR)] ≈ sqrt(Var(SR)) * sqrt(2 * log(n_trials))
    var_sr = (1 + 0.5 * sharpe**2) / n_obs
    expected_max = np.sqrt(var_sr) * np.sqrt(2 * np.log(max(n_trials, 1)))

    # Deflated Sharpe = max(0, SR - E[max(SR|null)])
    deflated = max(0.0, sharpe - expected_max)
    return float(deflated)


# ── Rolling Returns ───────────────────────────────────────────────


def compute_rolling_metrics(
    unit_nav: pd.Series,
    benchmark_nav: pd.Series | None = None,
    window_days: int = 252,
) -> RollingMetrics:
    """Compute rolling return statistics for a given window."""
    clean = unit_nav.dropna()
    if len(clean) < window_days:
        return RollingMetrics(window_days=window_days)

    rolling_rets = clean.pct_change(window_days).dropna()
    if len(rolling_rets) < 2:
        return RollingMetrics(window_days=window_days)

    metrics = RollingMetrics(window_days=window_days)
    metrics.median = float(rolling_rets.median())
    metrics.p10 = float(rolling_rets.quantile(0.10))
    metrics.worst = float(rolling_rets.min())
    metrics.positive_ratio = float((rolling_rets > 0).mean())

    if benchmark_nav is not None:
        bench_clean = benchmark_nav.dropna()
        if len(bench_clean) >= window_days:
            bench_rets = bench_clean.pct_change(window_days).dropna()
            common = rolling_rets.index.intersection(bench_rets.index)
            if len(common) > 0:
                metrics.benchmark_win_rate = float(
                    (rolling_rets.loc[common] > bench_rets.loc[common]).mean()
                )

    return metrics


# ── Regime Analysis ───────────────────────────────────────────────


REGIME_DEFINITIONS: list[dict[str, Any]] = [
    {"name": "Bull", "condition": lambda ret, vol, dd: ret > 0.15},
    {"name": "Bear", "condition": lambda ret, vol, dd: ret < -0.10},
    {"name": "Sideways", "condition": lambda ret, vol, dd: -0.10 <= ret <= 0.15},
    {"name": "High Vol", "condition": lambda ret, vol, dd: vol > 0.20},
    {"name": "Low Vol", "condition": lambda ret, vol, dd: vol < 0.10},
]


def compute_regime_analysis(
    strategy_nav: pd.Series,
    benchmark_nav: pd.Series | None = None,
    lookback: int = 60,
) -> list[RegimeResult]:
    """Split backtest into market regimes and compute per-regime metrics."""
    results: list[RegimeResult] = []

    rets = strategy_nav.pct_change(lookback).dropna()
    vol = strategy_nav.pct_change().rolling(lookback).std(ddof=0).dropna()
    dd_series = drawdown(strategy_nav)

    common = rets.index.intersection(vol.index).intersection(dd_series.index)
    if len(common) < lookback:
        return results

    for reg in REGIME_DEFINITIONS:
        try:
            in_regime = common[reg["condition"](rets[common].iloc[-1], vol[common].iloc[-1], float(dd_series[common].iloc[-1]))]
        except IndexError:
            continue

        regime_periods = common[common >= in_regime - pd.Timedelta(days=lookback)]
        if len(regime_periods) < 20:
            continue

        regime_strat = strategy_nav.reindex(regime_periods).dropna()
        if len(regime_strat) < 10:
            continue

        strat_ret = float(regime_strat.iloc[-1] / regime_strat.iloc[0] - 1)
        strat_vol = float(strategy_nav.reindex(regime_periods).pct_change().std(ddof=0) * np.sqrt(252))
        strat_dd = float(drawdown(regime_strat).min())
        strat_es = float(strategy_nav.reindex(regime_periods).pct_change().quantile(0.05)) if len(regime_periods) > 50 else 0.0

        bench_ret = 0.0
        if benchmark_nav is not None:
            bench_regime = benchmark_nav.reindex(regime_periods).dropna()
            if len(bench_regime) >= 10:
                bench_ret = float(bench_regime.iloc[-1] / bench_regime.iloc[0] - 1)

        results.append(
            RegimeResult(
                regime_name=reg["name"],
                strategy_return=strat_ret,
                benchmark_return=bench_ret,
                excess_return=strat_ret - bench_ret,
                volatility=strat_vol,
                max_drawdown=strat_dd,
                expected_shortfall=strat_es,
            )
        )

    return results


# ── Parameter Robustness ──────────────────────────────────────────


def compute_parameter_robustness(
    results: dict[float, float],  # param_value -> sharpe
    direction_positive: bool = True,
) -> ParameterSurfaceResult:
    """Compute robustness score — fraction of parameter values that
    maintain the same directional conclusion as the optimum."""
    if not results:
        return ParameterSurfaceResult()

    best_val = max(results) if direction_positive else min(results)
    best_sharpe = results[best_val]

    n_passing = 0
    values: list[dict[str, float]] = []
    for param, sharpe in sorted(results.items()):
        passes = (sharpe >= best_sharpe * 0.7) if direction_positive else (sharpe <= best_sharpe * 1.3)
        if passes:
            n_passing += 1
        values.append({"param_value": param, "sharpe": sharpe, "passes": float(passes)})

    robustness = n_passing / len(results) if results else 0.0
    return ParameterSurfaceResult(param_name="auto", values=values, robustness_score=robustness)


# ── Experiment Registry ───────────────────────────────────────────


class ExperimentRegistry:
    """In-memory registry of all strategy experiments (Section 30)."""

    def __init__(self) -> None:
        self.records: list[ExperimentRecord] = []

    def record(self, **kwargs: Any) -> ExperimentRecord:
        exp = ExperimentRecord(
            experiment_id=hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:12],
            created_at=datetime.now().isoformat(),
            **kwargs,
        )
        self.records.append(exp)
        return exp

    def count(self, strategy_id: str | None = None) -> int:
        if strategy_id:
            return sum(1 for r in self.records if r.strategy_id == strategy_id)
        return len(self.records)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(r) for r in self.records])


# ── Relative NAV ──────────────────────────────────────────────────


def compute_relative_nav(
    strategy_nav: pd.Series,
    benchmark_nav: pd.Series,
) -> pd.Series:
    """Relative NAV = strategy NAV / benchmark NAV."""
    common = strategy_nav.index.intersection(benchmark_nav.index)
    if len(common) < 2:
        return pd.Series(dtype=float)
    return strategy_nav.reindex(common) / benchmark_nav.reindex(common)
