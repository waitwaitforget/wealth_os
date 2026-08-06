"""Signal attribution — decompose TWR into value, trend, risk, and residual.

Each component's contribution is estimated by comparing a full-strategy
run against ablated runs that remove one component.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from wealth_os.domain.models import BacktestResult


@dataclass
class AttributionResult:
    """Decomposed return sources."""

    twr: float = 0.0
    value_contribution: float = 0.0
    trend_contribution: float = 0.0
    risk_contribution: float = 0.0
    cash_contribution: float = 0.0
    cost_drag: float = 0.0
    residual: float = 0.0
    total_orders: int = 0

    @property
    def explained(self) -> float:
        return self.value_contribution + self.trend_contribution + self.risk_contribution

    def summary(self) -> str:
        lines = ["Signal Attribution:"]
        lines.append(f"  TWR:               {self.twr:+.2%}")
        lines.append(f"  Value contribution: {self.value_contribution:+.2%}")
        lines.append(f"  Trend contribution: {self.trend_contribution:+.2%}")
        lines.append(f"  Risk contribution:  {self.risk_contribution:+.2%}")
        lines.append(f"  Cash contribution:  {self.cash_contribution:+.2%}")
        lines.append(f"  Cost drag:          {self.cost_drag:+.2%}")
        lines.append(f"  Residual:           {self.residual:+.2%}")
        return "\n".join(lines)


def attribute_signals(
    base_result: BacktestResult,
    value_only_result: BacktestResult | None = None,
    trend_only_result: BacktestResult | None = None,
    risk_only_result: BacktestResult | None = None,
    full_result: BacktestResult | None = None,
    cash_yield: float = 0.02,
) -> AttributionResult:
    """Decompose performance contributions.

    Args:
        base_result: Static strategy (no signals, no risk).
        value_only: Value-only strategy result.
        trend_only: Trend-only strategy result.
        full_result: Full VTR strategy result.
    """
    base_twr = _twr(base_result)
    val_twr = _twr(value_only_result) if value_only_result else base_twr
    trend_twr = _twr(trend_only_result) if trend_only_result else base_twr
    full_twr = _twr(full_result) if full_result else max(val_twr, trend_twr, base_twr)

    value_contribution = val_twr - base_twr
    trend_contribution = trend_twr - base_twr
    risk_contribution = full_twr - max(val_twr, trend_twr)  # risk scaling effect

    years = _years(base_result.nav)
    cash_contribution = (1 + cash_yield) ** years - 1
    if base_result is not None:
        avg_cash = float(base_result.cash.mean() / base_result.nav.mean())
        cash_contribution *= avg_cash

    cost_drag = 0.0
    if full_result is not None and full_result.transaction_costs is not None:
        total_cost = float(full_result.transaction_costs.sum())
        avg_nav = float(full_result.nav.mean()) if len(full_result.nav) > 0 else 1.0
        cost_drag = -total_cost / max(avg_nav, 1e-12)

    orders = (
        len(full_result.orders) if full_result is not None and full_result.orders is not None else 0
    )

    return AttributionResult(
        twr=full_twr,
        value_contribution=value_contribution,
        trend_contribution=trend_contribution,
        risk_contribution=risk_contribution,
        cash_contribution=cash_contribution,
        cost_drag=cost_drag,
        residual=full_twr
        - (base_twr + value_contribution + trend_contribution + risk_contribution),
        total_orders=orders,
    )


def _twr(result: BacktestResult) -> float:
    u = result.unit_nav.dropna()
    if len(u) <= 1:
        return 0.0
    return float(u.iloc[-1] / u.iloc[0] - 1)


def _years(series: pd.Series) -> float:
    return (
        max(float((series.index[-1] - series.index[0]).total_seconds() / 86400.0), 0.0) / 365.2425
    )
