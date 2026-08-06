"""Decision Engine — translates target weights into human-readable decisions.

Implements:
- Decision DTO with contribution decomposition
- Explanation engine (why each asset changes)
- Confidence scoring
- "No action" reasoning
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd


class ActionType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True)
class AssetDecision:
    """Single asset decision with decomposed contributions."""

    asset: str
    current_weight: float
    target_weight: float
    delta: float  # target - current
    action: ActionType
    priority: Priority

    # Signal contributions
    value_contribution: float = 0.0
    trend_contribution: float = 0.0
    risk_contribution: float = 0.0
    constraint_contribution: float = 0.0

    # Cost & confidence
    estimated_cost_bps: float = 0.0
    confidence: float = 0.8

    # Reasons
    reasons: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.action != ActionType.HOLD

    @property
    def signed_delta(self) -> str:
        return f"{self.delta:+.1%}"


@dataclass
class DecisionReport:
    """Complete decision report for one date."""

    date: pd.Timestamp
    strategy_id: str = ""
    strategy_version: str = "0.1.0"
    decisions: list[AssetDecision] = field(default_factory=list)
    trigger_reasons: list[str] = field(default_factory=list)
    portfolio_vol: float = 0.0
    drawdown: float = 0.0
    total_estimated_cost_bps: float = 0.0
    overall_confidence: float = 0.8
    is_no_action: bool = False

    @property
    def active_decisions(self) -> list[AssetDecision]:
        return [d for d in self.decisions if d.is_active]

    def summary(self) -> str:
        lines = [
            f"Decision Report: {self.date.date()}",
            f"  Strategy: {self.strategy_id} v{self.strategy_version}",
            f"  Portfolio Vol: {self.portfolio_vol:.2%}",
            f"  Drawdown: {self.drawdown:.2%}",
        ]

        if self.is_no_action:
            lines.append("  Action: NO ACTION")
            lines.append(f"  Reasons: {', '.join(self.trigger_reasons)}")
            return "\n".join(lines)

        lines.append(f"  Action: REBALANCE ({len(self.active_decisions)} trades)")
        lines.append(f"  Estimated Total Cost: {self.total_estimated_cost_bps:.1f} bps")
        lines.append(f"  Confidence: {self.overall_confidence:.0%}")
        lines.append(f"  Trigger: {', '.join(self.trigger_reasons)}")
        lines.append("")
        header = f"  {'Asset':<10} {'Cur':>7} {'Tgt':>7} {'Delta':>7} {'Act':>5} {'Pri':>5}"
        lines.append(header)
        lines.append("-" * 60)

        for d in self.decisions:
            if d.is_active:
                lines.append(
                    f"  {d.asset:<10} {d.current_weight:>7.1%} {d.target_weight:>7.1%} "
                    f"{d.signed_delta:>7} {d.action.value:>5} {d.priority.value:>5}"
                )

        return "\n".join(lines)


def generate_decision(
    date: pd.Timestamp,
    current_weights: pd.Series,
    target_weights: pd.Series,
    value_scores: pd.Series | None = None,
    trend_scores: pd.Series | None = None,
    volatility: pd.Series | None = None,
    base_weights: pd.Series | None = None,
    trigger_reasons: list[str] | None = None,
    portfolio_vol: float = 0.0,
    drawdown: float = 0.0,
    min_trade_fraction: float = 0.005,
    strategy_id: str = "",
) -> DecisionReport:
    """Generate a human-readable decision report from raw weights.

    Each asset's weight change is decomposed into value, trend,
    risk, and constraint contributions.
    """
    report = DecisionReport(
        date=date,
        strategy_id=strategy_id,
        trigger_reasons=trigger_reasons or [],
        portfolio_vol=portfolio_vol,
        drawdown=drawdown,
    )

    assets = list(set(current_weights.index) | set(target_weights.index))
    decisions: list[AssetDecision] = []
    total_cost = 0.0
    has_trade = False

    for sym in assets:
        cur = current_weights.get(sym, 0.0)
        tgt = target_weights.get(sym, 0.0)
        delta = tgt - cur

        if abs(delta) < min_trade_fraction:
            action = ActionType.HOLD
            priority = Priority.NONE
        elif delta > 0:
            action = ActionType.BUY
            priority = _priority(abs(delta))
            has_trade = True
        else:
            action = ActionType.SELL
            priority = _priority(abs(delta))
            has_trade = True

        # Decompose contributions
        val_c = 0.0
        trend_c = 0.0
        risk_c = 0.0
        const_c = 0.0
        reasons: list[str] = []

        if base_weights is not None and action != ActionType.HOLD:
            base_w = base_weights.get(sym, 0.0)
            if value_scores is not None and sym in value_scores:
                val_c = base_w * float(value_scores[sym]) * 0.4
                if abs(val_c) > 0.002:
                    reasons.append(f"Value signal: {val_c:+.2%}")
            if trend_scores is not None and sym in trend_scores:
                trend_c = base_w * float(trend_scores[sym]) * 0.4
                if abs(trend_c) > 0.002:
                    reasons.append(f"Trend signal: {trend_c:+.2%}")
            const_c = delta - val_c - trend_c

        estimated_cost = 0.0
        if action != ActionType.HOLD:
            notional = abs(delta)
            estimated_cost = notional * 10  # approximate 10 bps per unit traded
            total_cost += estimated_cost

        confidence = _confidence(abs(delta), portfolio_vol, len(reasons))

        decisions.append(
            AssetDecision(
                asset=sym,
                current_weight=cur,
                target_weight=tgt,
                delta=delta,
                action=action,
                priority=priority,
                value_contribution=val_c,
                trend_contribution=trend_c,
                risk_contribution=risk_c,
                constraint_contribution=const_c,
                estimated_cost_bps=estimated_cost,
                confidence=confidence,
                reasons=reasons,
            )
        )

    report.decisions = decisions
    report.total_estimated_cost_bps = total_cost
    report.is_no_action = not has_trade
    report.overall_confidence = (
        sum(d.confidence for d in decisions) / max(len(decisions), 1) if decisions else 1.0
    )

    return report


def generate_no_action_decision(
    date: pd.Timestamp,
    strategy_id: str = "",
    reasons: list[str] | None = None,
) -> DecisionReport:
    """Generate a no-action decision with explanations."""
    return DecisionReport(
        date=date,
        strategy_id=strategy_id,
        trigger_reasons=reasons or ["No trigger conditions met"],
        is_no_action=True,
        overall_confidence=1.0,
    )


def _priority(abs_delta: float) -> Priority:
    if abs_delta > 0.05:
        return Priority.HIGH
    if abs_delta > 0.02:
        return Priority.MEDIUM
    return Priority.LOW


def _confidence(abs_delta: float, portfolio_vol: float, n_reasons: int) -> float:
    base = 0.7
    if abs_delta > 0.03:
        base += 0.1
    if n_reasons >= 2:
        base += 0.1
    if portfolio_vol < 0.15:
        base += 0.05
    return min(base, 0.95)
