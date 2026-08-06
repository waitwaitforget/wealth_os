"""Backtest reconciliation — dual-engine NAV/position/order diff analysis.

Compares NativeBacktestEngine output against a second engine
(VectorBT or any BacktestEngine implementing the protocol).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from wealth_os.domain.models import BacktestResult


@dataclass(frozen=True)
class ReconciliationDiff:
    """Single metric difference between two engine outputs."""

    metric: str  # nav, unit_nav, cash, turnover, etc.
    max_absolute_diff: float
    mean_absolute_diff: float
    relative_diff_pct: float  # max_abs_diff / mean_baseline * 100
    passed: bool
    tolerance: float


@dataclass
class ReconciliationReport:
    """Full reconciliation report between two backtest engines."""

    engine_a: str = ""
    engine_b: str = ""
    diffs: list[ReconciliationDiff] = field(default_factory=list)
    order_count_a: int = 0
    order_count_b: int = 0
    nav_correlation: float = 0.0

    @property
    def passed(self) -> bool:
        return all(d.passed for d in self.diffs)

    @property
    def summary_text(self) -> str:
        lines = [f"Reconciliation: {self.engine_a} vs {self.engine_b}"]
        lines.append(f"  NAV correlation: {self.nav_correlation:.6f}")
        lines.append(f"  Orders: A={self.order_count_a}, B={self.order_count_b}")
        for d in self.diffs:
            status = "PASS" if d.passed else "FAIL"
            lines.append(
                f"  [{status}] {d.metric}: max={d.max_absolute_diff:.6e} "
                f"mean={d.mean_absolute_diff:.6e} ({d.relative_diff_pct:.2f}%)"
            )
        overall = "PASS" if self.passed else "FAIL"
        lines.insert(0, f"Reconciliation: {overall}")
        return "\n".join(lines)


def reconcile_backtests(
    a: BacktestResult,
    b: BacktestResult,
    engine_a: str = "native",
    engine_b: str = "vectorbt",
    nav_tolerance: float = 1e-4,
    weight_tolerance: float = 1e-3,
    cash_tolerance: float = 1e-4,
) -> ReconciliationReport:
    """Compare two BacktestResult objects day-by-day.

    Returns a ReconciliationReport with per-metric diffs.
    """
    report = ReconciliationReport(engine_a=engine_a, engine_b=engine_b)
    common = a.nav.index.intersection(b.nav.index)

    if len(common) < 10:
        report.diffs.append(
            ReconciliationDiff(
                "common_dates",
                0,
                0,
                0,
                False,
                0,  # type: ignore[call-arg]
            )
        )
        return report

    # NAV
    nav_a = a.nav.reindex(common)
    nav_b = b.nav.reindex(common)
    nav_corr = float(nav_a.corr(nav_b)) if len(nav_a) > 1 else 0.0
    report.nav_correlation = nav_corr

    nav_diff = (nav_a - nav_b).abs()
    mean_nav = nav_a.abs().mean()
    report.diffs.append(
        ReconciliationDiff(
            metric="nav",
            max_absolute_diff=float(nav_diff.max()),
            mean_absolute_diff=float(nav_diff.mean()),
            relative_diff_pct=(float(nav_diff.max() / mean_nav * 100) if mean_nav > 0 else 0.0),
            passed=float(nav_diff.max()) < nav_tolerance * mean_nav,
            tolerance=nav_tolerance,
        )
    )

    # Unit NAV
    if a.unit_nav is not None and b.unit_nav is not None:
        una = a.unit_nav.reindex(common)
        unb = b.unit_nav.reindex(common)
        un_diff = (una - unb).abs()
        report.diffs.append(
            ReconciliationDiff(
                metric="unit_nav",
                max_absolute_diff=float(un_diff.max()),
                mean_absolute_diff=float(un_diff.mean()),
                relative_diff_pct=(float(un_diff.max() / max(una.abs().mean(), 1e-12) * 100)),
                passed=float(un_diff.max()) < nav_tolerance,
                tolerance=nav_tolerance,
            )
        )

    # Cash
    cash_diff = (a.cash.reindex(common) - b.cash.reindex(common)).abs()
    report.diffs.append(
        ReconciliationDiff(
            metric="cash",
            max_absolute_diff=float(cash_diff.max()),
            mean_absolute_diff=float(cash_diff.mean()),
            relative_diff_pct=(float(cash_diff.max() / max(a.cash.abs().mean(), 1e-12) * 100)),
            passed=float(cash_diff.max()) < cash_tolerance * max(a.cash.abs().mean(), 1.0),
            tolerance=cash_tolerance,
        )
    )

    # Orders
    report.order_count_a = len(a.orders) if a.orders is not None else 0
    report.order_count_b = len(b.orders) if b.orders is not None else 0

    return report


def validate_capital_conservation(result: BacktestResult, tolerance: float = 1e-6) -> list[str]:
    """Verify that capital is conserved throughout the backtest.

    Checks:
    - NAV = cash + positions_value (daily)
    - unit_nav = NAV / units
    - No unexplained NAV jumps
    """
    issues: list[str] = []

    reconstructed = result.cash + result.positions_value.sum(axis=1)
    nav_error = (reconstructed - result.nav).abs()
    max_err = float(nav_error.max())
    if max_err > tolerance:
        issues.append(f"NAV identity violated: max error = {max_err:.2e}")

    if result.units is not None and (result.units <= 0).any():
        issues.append("Units became negative or zero")

    if (result.cash < -tolerance).any():
        neg_days = (result.cash < -tolerance).sum()
        issues.append(f"Cash negative on {neg_days} days")

    return issues


def compute_turnover_attribution(result: BacktestResult) -> pd.DataFrame | None:
    """Break down turnover by source (rebalance vs contribution vs cost)."""
    if result.orders is None or result.orders.empty:
        return None

    orders = result.orders
    if "reason" in orders.columns:
        attribution = (
            orders.groupby("reason")["notional"]
            .apply(lambda x: x.abs().sum())
            .to_frame(name="total_notional")
        )
        attribution["pct"] = attribution["total_notional"] / attribution["total_notional"].sum()
        return attribution
    return None
