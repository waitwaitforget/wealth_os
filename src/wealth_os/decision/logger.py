"""Decision Logger — records, replays, and reviews past decisions.

Tracks:
- Every decision snapshot for audit
- Suggested vs actual execution deviation
- Historical decision review
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from wealth_os.decision.engine import DecisionReport


@dataclass
class DecisionLog:
    """Immutable record of a single decision."""

    decision: DecisionReport
    actual_weights_after: pd.Series | None = None
    execution_cost_bps: float = 0.0
    timestamp: pd.Timestamp = field(default_factory=pd.Timestamp.now)


@dataclass
class DecisionLogger:
    """Persistent audit trail of all strategy decisions."""

    logs: list[DecisionLog] = field(default_factory=list)
    strategy_id: str = ""

    def record(
        self,
        decision: DecisionReport,
        actual_weights_after: pd.Series | None = None,
        execution_cost_bps: float = 0.0,
    ) -> None:
        self.logs.append(
            DecisionLog(
                decision=decision,
                actual_weights_after=actual_weights_after,
                execution_cost_bps=execution_cost_bps,
            )
        )

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for log in self.logs:
            d = log.decision
            n_trades = len(d.active_decisions)
            rows.append(
                {
                    "date": d.date,
                    "n_trades": n_trades,
                    "estimated_cost_bps": d.total_estimated_cost_bps,
                    "actual_cost_bps": log.execution_cost_bps,
                    "is_no_action": d.is_no_action,
                    "confidence": d.overall_confidence,
                    "trigger": "; ".join(d.trigger_reasons),
                }
            )
        return pd.DataFrame(rows)

    def to_jsonl(self, path: str | Path) -> None:
        """Save logs to a JSONL file for audit."""
        with open(path, "w") as f:
            for log in self.logs:
                d = log.decision
                record: dict[str, Any] = {
                    "date": str(d.date.date()),
                    "strategy_id": d.strategy_id,
                    "n_trades": len(d.active_decisions),
                    "est_cost_bps": d.total_estimated_cost_bps,
                    "actual_cost_bps": log.execution_cost_bps,
                    "is_no_action": d.is_no_action,
                    "confidence": d.overall_confidence,
                    "trigger": d.trigger_reasons,
                    "decisions": [
                        {
                            "asset": dd.asset,
                            "current": dd.current_weight,
                            "target": dd.target_weight,
                            "action": dd.action.value,
                            "priority": dd.priority.value,
                            "value_contribution": dd.value_contribution,
                            "trend_contribution": dd.trend_contribution,
                        }
                        for dd in d.decisions
                    ],
                }
                f.write(json.dumps(record, default=str) + "\n")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> DecisionLogger:
        logger = cls()
        with open(path) as f:
            for line in f:
                logger.logs.append(json.loads(line))
        return logger

    def review(self) -> dict[str, float]:
        """Summarize decision history statistics."""
        if not self.logs:
            return {}

        df = self.to_dataframe()
        n_total = len(df)
        n_trades = df["n_trades"].sum()
        n_no_action = df["is_no_action"].sum()
        avg_cost = df["estimated_cost_bps"].mean()
        avg_confidence = df["confidence"].mean()

        cost_slippage = 0.0
        if df.shape[0] > 1:
            actual = df["actual_cost_bps"]
            estimated = df["estimated_cost_bps"]
            cost_slippage = float((actual - estimated).mean()) if not actual.isna().all() else 0.0

        return {
            "total_decisions": n_total,
            "total_trades": int(n_trades),
            "no_action_pct": n_no_action / max(n_total, 1),
            "avg_est_cost_bps": avg_cost,
            "avg_confidence": avg_confidence,
            "cost_slippage_bps": cost_slippage,
        }


def compute_execution_deviation(
    suggested_weights: pd.DataFrame,
    actual_weights: pd.DataFrame,
) -> pd.DataFrame:
    """Compare suggested target weights vs actual executed weights over time.

    Returns DataFrame with per-date deviation metrics.
    """
    common_idx = suggested_weights.index.intersection(actual_weights.index)
    if len(common_idx) < 2:
        return pd.DataFrame()

    suggested = suggested_weights.reindex(common_idx)
    actual = actual_weights.reindex(common_idx)

    deviation = (actual - suggested).abs()
    result = pd.DataFrame(index=common_idx)
    result["total_abs_deviation"] = deviation.sum(axis=1)
    result["max_single_deviation"] = deviation.max(axis=1)
    result["n_assets_deviated"] = (deviation > 0.005).sum(axis=1)

    return result
