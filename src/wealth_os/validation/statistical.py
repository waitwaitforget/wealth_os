"""Statistical validation — walk-forward, bootstrap, ablation, stress tests.

Verifies strategy results are not artifacts of a single parameter,
time period, or data path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wealth_os.domain.models import BacktestResult


@dataclass
class StatisticalReport:
    """Aggregated statistical validation results."""

    metrics: dict[str, float] = field(default_factory=dict)
    details: dict[str, object] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    def summary(self) -> str:
        if not self.issues:
            return f"Statistical Validation: PASS ({len(self.metrics)} metrics)"
        lines = [f"Statistical Validation: {len(self.issues)} issues"]
        for i in self.issues:
            lines.append(f"  - {i}")
        return "\n".join(lines)


# ── Walk-Forward ──────────────────────────────────────────────────


def walk_forward(
    run_fn: Callable[[pd.DataFrame], BacktestResult],
    prices: pd.DataFrame,
    train_window: int = 756,  # ~3 years
    test_window: int = 252,  # ~1 year
    step: int = 63,  # ~3 months
) -> list[dict[str, object]]:
    """Walk-forward backtest with rolling windows.

    Returns list of {twr, sharpe, max_dd, start, end} per fold.
    """
    results: list[dict[str, object]] = []
    start_idx = 0

    while start_idx + train_window + test_window <= len(prices):
        train_end = start_idx + train_window
        test_end = train_end + test_window

        window_prices = prices.iloc[train_end:test_end]
        if len(window_prices) < 50:
            break

        result = run_fn(window_prices)
        unit_nav = result.unit_nav.dropna()

        if len(unit_nav) > 10:
            rets = unit_nav.pct_change().dropna()
            twr = float(unit_nav.iloc[-1] / unit_nav.iloc[0] - 1)
            ann_vol = float(rets.std(ddof=0) * np.sqrt(252))
            sharpe = float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)) if ann_vol > 0 else 0.0
            peak = unit_nav.expanding().max()
            max_dd = float((unit_nav / peak - 1.0).min())

            results.append(
                {
                    "twr": twr,
                    "sharpe": sharpe,
                    "max_dd": max_dd,
                    "start": str(prices.index[train_end].date()),
                    "end": str(prices.index[test_end - 1].date()),
                }
            )

        start_idx += step

    return results


def walk_forward_report(results: list[dict[str, float]]) -> StatisticalReport:
    """Analyze walk-forward results for stability."""
    report = StatisticalReport()

    if not results:
        report.issues.append("No walk-forward folds produced")
        return report

    twrs = [r["twr"] for r in results]
    sharpes = [r["sharpe"] for r in results]
    max_dds = [r["max_dd"] for r in results]

    report.metrics["n_folds"] = float(len(results))
    report.metrics["twr_mean"] = float(np.mean(twrs))
    report.metrics["twr_std"] = float(np.std(twrs, ddof=1))
    report.metrics["sharpe_mean"] = float(np.mean(sharpes))
    report.metrics["sharpe_std"] = float(np.std(sharpes, ddof=1))
    report.metrics["max_dd_mean"] = float(np.mean(max_dds))

    if report.metrics["sharpe_mean"] < 0:
        report.issues.append("Negative average Sharpe across folds")

    positive_folds = sum(1 for t in twrs if t > 0)
    report.metrics["positive_fold_pct"] = float(positive_folds) / len(results)

    if report.metrics["positive_fold_pct"] < 0.5:
        report.issues.append(f"Only {positive_folds}/{len(results)} folds profitable")

    report.details["fold_dates"] = f"{results[0]['start']} → {results[-1]['end']}"

    return report


# ── Ablation ──────────────────────────────────────────────────────


def ablation_test(
    run_fn_full: Callable[[], BacktestResult],
    run_fn_without: dict[str, Callable[[], BacktestResult]],
) -> StatisticalReport:
    """Test impact of removing each component.

    Args:
        run_fn_full: Full strategy run.
        run_fn_without: {component_name: run_fn_without_component}
    """
    report = StatisticalReport()

    try:
        full = run_fn_full()
        full_sharpe = _extract_sharpe(full)
        report.metrics["full_sharpe"] = full_sharpe

        for name, run_fn in run_fn_without.items():
            try:
                ablated = run_fn()
                ablated_sharpe = _extract_sharpe(ablated)
                delta = ablated_sharpe - full_sharpe
                report.metrics[f"ablation_{name}_sharpe"] = ablated_sharpe
                report.metrics[f"ablation_{name}_delta"] = delta

                if ablated_sharpe > full_sharpe + 0.2:
                    report.issues.append(
                        f"Removing '{name}' improved Sharpe by {delta:.3f} (may be harmful)"
                    )
            except Exception as e:
                report.issues.append(f"Ablation '{name}' failed: {e}")

    except Exception as e:
        report.issues.append(f"Full run failed: {e}")

    return report


# ── Bootstrap ─────────────────────────────────────────────────────


def bootstrap_metrics(
    unit_nav: pd.Series,
    n_bootstrap: int = 500,
    block_size: int = 20,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """Block bootstrap of strategy returns.

    Returns {metric: {mean, std, ci_lower, ci_upper}}.
    """
    rng = np.random.default_rng(seed)
    rets = unit_nav.pct_change().dropna().values

    if len(rets) < block_size * 2:
        return {}

    sharpe_samples: list[float] = []
    ann_ret_samples: list[float] = []

    for _ in range(n_bootstrap):
        n_blocks = len(rets) // block_size
        indices = rng.integers(0, len(rets) - block_size, size=n_blocks)
        sample = np.concatenate([rets[i : i + block_size] for i in indices])

        ann_ret = float(sample.mean() * 252)
        ann_vol = float(sample.std(ddof=0) * np.sqrt(252))
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0

        ann_ret_samples.append(ann_ret)
        sharpe_samples.append(sharpe)

    sharpe_arr = np.array(sharpe_samples)
    ret_arr = np.array(ann_ret_samples)

    return {
        "sharpe": {
            "mean": float(sharpe_arr.mean()),
            "std": float(sharpe_arr.std()),
            "ci_lower": float(np.percentile(sharpe_arr, 5)),
            "ci_upper": float(np.percentile(sharpe_arr, 95)),
        },
        "annualized_return": {
            "mean": float(ret_arr.mean()),
            "std": float(ret_arr.std()),
            "ci_lower": float(np.percentile(ret_arr, 5)),
            "ci_upper": float(np.percentile(ret_arr, 95)),
        },
    }


# ── Cost Stress ───────────────────────────────────────────────────


@dataclass
class CostStressReport:
    base_metrics: dict[str, float]
    stressed_metrics: dict[str, float]
    cost_multiplier: float

    def summary(self) -> str:
        lines = [f"Cost Stress ({self.cost_multiplier}x costs):"]
        for k in self.base_metrics:
            b = self.base_metrics[k]
            s = self.stressed_metrics.get(k, float("nan"))
            delta = s - b if not np.isnan(s) else float("nan")
            lines.append(f"  {k}: {b:.4f} → {s:.4f} (Δ={delta:+.4f})")
        return "\n".join(lines)


def cost_stress_test(
    run_fn: Callable[[float], BacktestResult],
    base_cost_mult: float = 1.0,
    stress_cost_mult: float = 2.0,
) -> CostStressReport:
    """Compare strategy performance under baseline vs stressed costs."""
    base = run_fn(base_cost_mult)
    stressed = run_fn(stress_cost_mult)

    def _metrics(r: BacktestResult) -> dict[str, float]:
        unit = r.unit_nav.dropna()
        rets = unit.pct_change().dropna()
        if len(rets) < 10:
            return {}
        twr = float(unit.iloc[-1] / unit.iloc[0] - 1)
        sharpe = float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)) if rets.std() > 0 else 0.0
        peak = unit.expanding().max()
        max_dd = float((unit / peak - 1.0).min())
        return {"twr": twr, "sharpe": sharpe, "max_dd": max_dd}

    return CostStressReport(
        base_metrics=_metrics(base),
        stressed_metrics=_metrics(stressed),
        cost_multiplier=stress_cost_mult,
    )


# ── Helpers ───────────────────────────────────────────────────────


def _extract_sharpe(result: BacktestResult) -> float:
    unit = result.unit_nav.dropna()
    rets = unit.pct_change().dropna()
    if rets.std() > 0:
        return float(rets.mean() / rets.std(ddof=0) * np.sqrt(252))
    return 0.0
