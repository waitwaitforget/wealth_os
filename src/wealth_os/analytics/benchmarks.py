"""Benchmark definitions and comparison system.

Provides standard benchmarks for strategy evaluation:
- Static strategic weights (fixed, no rebalance)
- Equal weight
- 60/40 stocks/bonds proxy
- Single-market benchmarks
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wealth_os.analytics.performance import performance_summary
from wealth_os.domain.models import BacktestResult


@dataclass
class Benchmark:
    name: str
    weights: dict[str, float]
    description: str = ""


COMMON_BENCHMARKS: list[Benchmark] = [
    Benchmark(
        name="Equal Weight",
        weights={},
        description="All non-cash assets equally weighted",
    ),
    Benchmark(
        name="60/40 Stocks/Bonds",
        weights={},
        description="Classic 60% equity 40% bond portfolio",
    ),
    Benchmark(
        name="Global Market Cap",
        weights={"US": 0.55, "CN": 0.25, "HK": 0.10, "Gold": 0.05, "Cash": 0.05},
        description="Approximate global market cap weights",
    ),
]


@dataclass
class BenchmarkResult:
    benchmark_name: str
    metrics: dict[str, float]
    active_return: float = 0.0  # strategy TWR - benchmark TWR
    tracking_error: float = 0.0
    information_ratio: float = 0.0


@dataclass
class BenchmarkComparison:
    """Compare a strategy result against multiple benchmarks."""

    strategy_name: str = ""
    results: list[BenchmarkResult] = field(default_factory=list)

    def add_benchmark(
        self,
        name: str,
        bench_nav: pd.Series,
        strategy_nav: pd.Series,
    ) -> None:
        bench_metrics = performance_summary(bench_nav, initial_unit_nav=1.0)
        strategy_twr = float(strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1)
        bench_twr = bench_metrics["twr"]
        active_return = strategy_twr - bench_twr

        common = strategy_nav.index.intersection(bench_nav.index)
        if len(common) > 10:
            strat_ret = strategy_nav.reindex(common).pct_change().dropna()
            bench_ret = bench_nav.reindex(common).pct_change().dropna()
            diff = strat_ret - bench_ret
            tracking_error = float(diff.std(ddof=0) * np.sqrt(252)) if len(diff) > 1 else 0.0
            information_ratio = active_return / tracking_error if tracking_error > 0 else 0.0
        else:
            tracking_error = 0.0
            information_ratio = 0.0

        self.results.append(
            BenchmarkResult(
                benchmark_name=name,
                metrics=bench_metrics,
                active_return=active_return,
                tracking_error=tracking_error,
                information_ratio=information_ratio,
            )
        )

    def summary(self) -> str:
        lines = [f"{'=' * 70}", f"  Benchmark Comparison: {self.strategy_name}", f"{'=' * 70}"]
        lines.append(
            f"{'Benchmark':<22} {'Strat TWR':>10} {'Bench TWR':>10} "
            f"{'Active':>8} {'TE':>8} {'IR':>7}"
        )
        lines.append("-" * 70)

        for r in self.results:
            strat_twr = r.metrics.get("twr", 0.0) + r.active_return
            lines.append(
                f"{r.benchmark_name:<22} {strat_twr:>10.2%} "
                f"{r.metrics.get('twr', 0.0):>10.2%} "
                f"{r.active_return:>+8.2%} "
                f"{r.tracking_error:>8.2%} "
                f"{r.information_ratio:>7.3f}"
            )
        return "\n".join(lines)


def compute_market_benchmark_nav(
    prices: pd.DataFrame,
    weights: dict[str, float],
    initial_value: float = 1.0,
) -> pd.Series:
    """Compute a passive benchmark NAV series from price data and weights."""
    if not weights:
        return pd.Series(dtype=float)

    available = {k: v for k, v in weights.items() if k in prices.columns}
    if not available:
        return pd.Series(dtype=float)

    total = sum(available.values())
    norm_w = pd.Series({k: v / total for k, v in available.items()})

    nav = pd.Series(index=prices.index, dtype=float)
    nav.iloc[0] = initial_value

    for i in range(1, len(prices)):
        prev_nav = nav.iloc[i - 1]
        ret = 0.0
        for sym, w in norm_w.items():
            if sym in prices.columns:
                asset_ret = (
                    prices[sym].iloc[i] / prices[sym].iloc[i - 1] - 1
                    if prices[sym].iloc[i - 1] > 0
                    else 0.0
                )
                ret += w * asset_ret
        nav.iloc[i] = prev_nav * (1 + ret)

    return nav.dropna()


def compare_to_benchmarks(
    strategy_result: BacktestResult,
    prices: pd.DataFrame,
    strategy_name: str = "Strategy",
) -> BenchmarkComparison:
    """Compare a strategy result against standard benchmarks."""
    comp = BenchmarkComparison(strategy_name=strategy_name)

    safe_prices = prices.reindex(strategy_result.unit_nav.index).ffill()
    strat_nav = strategy_result.unit_nav.dropna()

    # Static strategic weights (no rebalance)
    if len(safe_prices.columns) >= 2:
        non_cash = [c for c in safe_prices.columns if "CASH" not in c.upper()]
        static_weights = {c: 1.0 / len(non_cash) for c in non_cash} if non_cash else {}
        bench_nav = compute_market_benchmark_nav(safe_prices, static_weights)
        if not bench_nav.empty:
            comp.add_benchmark("Equal Weight", bench_nav, strat_nav)

    # 60/40 proxy
    if len(safe_prices.columns) >= 2:
        equity_cols = [c for c in safe_prices.columns if "CASH" not in c.upper()][:2]
        if equity_cols:
            w60 = {equity_cols[0]: 0.6, equity_cols[-1]: 0.4}
            bench_nav_60 = compute_market_benchmark_nav(safe_prices, w60)
            if not bench_nav_60.empty:
                comp.add_benchmark("60/40 Stocks", bench_nav_60, strat_nav)

    return comp
