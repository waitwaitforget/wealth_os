"""Execution reconciliation, slippage analysis, and live alerts.

Compares model-expected vs broker-actual execution:
- Fill price vs reference price
- Execution cost breakdown
- Model vs actual position reconciliation
- Anomaly detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pandas as pd

from wealth_os.execution.broker import Order, OrderStatus


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ExecutionAlert:
    level: AlertLevel
    message: str
    timestamp: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    details: dict = field(default_factory=dict)


@dataclass
class SlippageReport:
    """Analyze execution slippage across orders."""

    orders: list[Order] = field(default_factory=list)

    @property
    def avg_slippage_bps(self) -> float:
        filled = [o for o in self.orders if o.is_filled and o.slippage_bps > 0]
        if not filled:
            return 0.0
        return float(np.mean([o.slippage_bps for o in filled]))

    @property
    def max_slippage_bps(self) -> float:
        return max((o.slippage_bps for o in self.orders if o.is_filled), default=0.0)

    @property
    def total_commission(self) -> float:
        return sum(o.commission for o in self.orders)

    @property
    def fill_rate(self) -> float:
        filled = [o for o in self.orders if o.is_filled]
        total = len(self.orders)
        return len(filled) / max(total, 1)

    def by_symbol(self) -> pd.DataFrame:
        """Per-symbol slippage summary."""
        records = []
        for o in self.orders:
            if o.is_filled:
                records.append(
                    {
                        "symbol": o.symbol,
                        "side": o.side.value,
                        "notional": o.notional,
                        "slippage_bps": o.slippage_bps,
                        "commission": o.commission,
                    }
                )
        if not records:
            return pd.DataFrame()
        return (
            pd.DataFrame(records)
            .groupby("symbol")
            .agg({"notional": "sum", "slippage_bps": "mean", "commission": "sum"})
        )

    def summary(self) -> str:
        lines = [
            f"Slippage Report: {len(self.orders)} orders",
            f"  Avg slippage: {self.avg_slippage_bps:.1f} bps",
            f"  Max slippage: {self.max_slippage_bps:.1f} bps",
            f"  Total commission: {self.total_commission:.2f}",
            f"  Fill rate: {self.fill_rate:.1%}",
        ]
        return "\n".join(lines)


def reconcile_model_vs_actual(
    model_weights: pd.Series,
    actual_positions: dict[str, float],
    prices: pd.Series,
    nav: float,
) -> dict[str, dict[str, float]]:
    """Compare model target weights vs actual broker positions.

    Returns per-asset dict with {model_w, actual_w, deviation}.
    """
    result: dict[str, dict[str, float]] = {}
    all_syms = set(model_weights.index) | set(actual_positions)

    for sym in all_syms:
        model_w = float(model_weights.get(sym, 0.0))
        actual_w = actual_positions.get(sym, 0.0) * prices.get(sym, 0.0) / nav if nav > 0 else 0.0
        result[sym] = {
            "model_weight": model_w,
            "actual_weight": actual_w,
            "deviation": actual_w - model_w,
            "is_deviated": abs(actual_w - model_w) > 0.02,
        }

    total_deviation = sum(abs(v["deviation"]) for v in result.values())
    result["_total"] = {
        "model_weight": 1.0,
        "actual_weight": 1.0,
        "deviation": total_deviation,
        "is_deviated": total_deviation > 0.05,
    }

    return result


class ExecutionMonitor:
    """Live monitoring for execution quality and anomalies."""

    def __init__(
        self, max_slippage_warn_bps: float = 20.0, max_slippage_crit_bps: float = 50.0
    ) -> None:
        self.max_slippage_warn = max_slippage_warn_bps
        self.max_slippage_crit = max_slippage_crit_bps
        self.alerts: list[ExecutionAlert] = []

    def check_order(self, order: Order, reference_price: float) -> list[ExecutionAlert]:
        new_alerts: list[ExecutionAlert] = []

        if order.status == OrderStatus.REJECTED:
            new_alerts.append(
                ExecutionAlert(
                    AlertLevel.CRITICAL,
                    f"Order {order.order_id} ({order.symbol}) rejected",
                    details={"order_id": order.order_id, "reason": "rejected"},
                )
            )

        if order.is_filled and order.slippage_bps > 0:
            slippage = order.slippage_bps
            if slippage > self.max_slippage_crit:
                new_alerts.append(
                    ExecutionAlert(
                        AlertLevel.CRITICAL,
                        f"CRITICAL slippage on {order.symbol}: {slippage:.1f} bps",
                        details={"symbol": order.symbol, "slippage": slippage},
                    )
                )
            elif slippage > self.max_slippage_warn:
                new_alerts.append(
                    ExecutionAlert(
                        AlertLevel.WARNING,
                        f"High slippage on {order.symbol}: {slippage:.1f} bps",
                        details={"symbol": order.symbol, "slippage": slippage},
                    )
                )

        if order.is_filled and order.fill_rate < 0.5:
            new_alerts.append(
                ExecutionAlert(
                    AlertLevel.WARNING,
                    f"Low fill rate for {order.symbol}: {order.fill_rate:.1%}",
                    details={"symbol": order.symbol, "fill_rate": order.fill_rate},
                )
            )

        self.alerts.extend(new_alerts)
        return new_alerts

    def check_reconciliation(
        self,
        reconciliation: dict[str, dict[str, float]],
    ) -> list[ExecutionAlert]:
        new_alerts: list[ExecutionAlert] = []

        for sym, data in reconciliation.items():
            if sym == "_total":
                continue
            if data["is_deviated"]:
                new_alerts.append(
                    ExecutionAlert(
                        AlertLevel.WARNING,
                        f"Position deviation on {sym}: {data['deviation']:+.2%}",
                        details={"symbol": sym, "deviation": data["deviation"]},
                    )
                )

        total = reconciliation.get("_total", {})
        if total.get("is_deviated"):
            new_alerts.append(
                ExecutionAlert(
                    AlertLevel.CRITICAL,
                    "Total portfolio deviation exceeds 5%",
                    details={"total_deviation": total.get("deviation", 0.0)},
                )
            )

        self.alerts.extend(new_alerts)
        return new_alerts

    def summary(self) -> str:
        if not self.alerts:
            return "No alerts."
        crit = sum(1 for a in self.alerts if a.level == AlertLevel.CRITICAL)
        warn = sum(1 for a in self.alerts if a.level == AlertLevel.WARNING)
        info = sum(1 for a in self.alerts if a.level == AlertLevel.INFO)
        lines = [f"Alerts: {crit} critical, {warn} warning, {info} info"]
        for a in self.alerts[-5:]:  # show last 5
            lines.append(f"  [{a.level.value}] {a.message}")
        return "\n".join(lines)
