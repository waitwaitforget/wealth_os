"""Strategy lifecycle governance — Shadow Portfolio, strategy states, audit.

Implements:
- Strategy state machine (Research → Candidate → Shadow → Production → Retired)
- Shadow Portfolio (model-only, no execution)
- Strategy version audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import numpy as np
import pandas as pd


class StrategyState(StrEnum):
    RESEARCH = "research"
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    LIMITED_CAPITAL = "limited_capital"
    PRODUCTION = "production"
    REVIEW = "review"
    SUSPENDED = "suspended"
    RETIRED = "retired"


ALLOWED_TRANSITIONS: dict[StrategyState, list[StrategyState]] = {
    StrategyState.RESEARCH: [StrategyState.CANDIDATE, StrategyState.RETIRED],
    StrategyState.CANDIDATE: [StrategyState.SHADOW, StrategyState.RESEARCH, StrategyState.RETIRED],
    StrategyState.SHADOW: [
        StrategyState.LIMITED_CAPITAL,
        StrategyState.CANDIDATE,
        StrategyState.SUSPENDED,
        StrategyState.RETIRED,
    ],
    StrategyState.LIMITED_CAPITAL: [
        StrategyState.PRODUCTION,
        StrategyState.SHADOW,
        StrategyState.SUSPENDED,
    ],
    StrategyState.PRODUCTION: [
        StrategyState.REVIEW,
        StrategyState.LIMITED_CAPITAL,
        StrategyState.SUSPENDED,
    ],
    StrategyState.REVIEW: [
        StrategyState.PRODUCTION,
        StrategyState.SUSPENDED,
        StrategyState.RETIRED,
    ],
    StrategyState.SUSPENDED: [StrategyState.SHADOW, StrategyState.RETIRED],
    StrategyState.RETIRED: [],
}

STATE_REQUIREMENTS: dict[StrategyState, list[str]] = {
    StrategyState.CANDIDATE: [
        "Backtest validation passed",
        "Data quality report clean",
        "Factor validation passed",
    ],
    StrategyState.SHADOW: [
        "Shadow run >= 60 trading days",
        "No accounting errors",
        "Reconciliation within tolerance",
    ],
    StrategyState.LIMITED_CAPITAL: ["At least 2 months shadow with positive Sharpe"],
    StrategyState.PRODUCTION: [
        "Human approval required",
        "Risk limits reviewed",
        "Rollback plan documented",
    ],
}


@dataclass
class StrategyTransition:
    from_state: StrategyState
    to_state: StrategyState
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    approved_by: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyLifecycle:
    """Manages a strategy through its lifecycle states.

    Enforces valid transitions and records an immutable audit trail.
    """

    strategy_id: str
    strategy_version: str = "0.1.0"
    current_state: StrategyState = StrategyState.RESEARCH
    history: list[StrategyTransition] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def can_transition(self, to: StrategyState) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, [])
        return to in allowed

    def transition(
        self,
        to: StrategyState,
        reason: str = "",
        approved_by: str = "",
        force: bool = False,
    ) -> bool:
        if not force and not self.can_transition(to):
            return False

        transition = StrategyTransition(
            from_state=self.current_state,
            to_state=to,
            reason=reason,
            approved_by=approved_by,
        )
        self.history.append(transition)
        self.current_state = to
        return True

    def requirements_for(self, state: StrategyState) -> list[str]:
        return STATE_REQUIREMENTS.get(state, [])

    def audit_trail(self) -> list[dict]:
        return [
            {
                "from": t.from_state,
                "to": t.to_state,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "approved_by": t.approved_by,
            }
            for t in self.history
        ]

    def summary(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "version": self.strategy_version,
            "state": str(self.current_state),
            "transitions": len(self.history),
            "created_at": self.created_at.isoformat(),
        }


# ── Shadow Portfolio ──────────────────────────────────────────────


@dataclass
class ShadowPortfolio:
    """Tracks a model-only portfolio that mirrors strategy decisions
    without execution.  Used to compare model vs actual performance.
    """

    strategy_id: str
    initial_capital: float = 1_000_000.0
    cash: float = 1_000_000.0
    positions: dict[str, float] = field(default_factory=dict)
    nav_history: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    order_history: list[dict] = field(default_factory=list)

    def record_snapshot(
        self,
        date: pd.Timestamp,
        prices: pd.Series,
        cash: float,
    ) -> float:
        """Record portfolio value at a date and return NAV."""
        self.cash = cash
        position_value = sum(
            self.positions.get(sym, 0) * prices.get(sym, 0) for sym in self.positions
        )
        nav = float(cash + position_value)
        self.nav_history.append((date, nav))
        return nav

    def record_rebalance(
        self,
        date: pd.Timestamp,
        target_weights: pd.Series,
        prices: pd.Series,
        nav: float,
        cost: float = 0.0,
    ) -> None:
        """Simulate a rebalance without executing."""
        for sym, w in target_weights.items():
            if sym in prices and prices[sym] > 0:
                self.positions[sym] = w * nav / prices[sym]

        self.order_history.append(
            {
                "date": date,
                "action": "rebalance",
                "target_weights": target_weights.to_dict(),
                "nav": nav,
                "cost": cost,
            }
        )

    def to_nav_series(self) -> pd.Series:
        if not self.nav_history:
            return pd.Series(dtype=float)
        dates, values = zip(*self.nav_history, strict=True)
        return pd.Series(values, index=pd.DatetimeIndex(dates))


# ── Deviation Analysis ────────────────────────────────────────────


def analyze_model_vs_actual_deviation(
    model_nav: pd.Series,
    actual_nav: pd.Series,
) -> dict[str, float]:
    """Compare model (shadow) vs actual portfolio performance.

    Returns deviation metrics: tracking error, return difference, etc.
    """
    common = model_nav.index.intersection(actual_nav.index)
    if len(common) < 10:
        return {}

    m = model_nav.reindex(common)
    a = actual_nav.reindex(common)

    model_rets = m.pct_change().dropna()
    actual_rets = a.pct_change().dropna()
    diff_rets = model_rets - actual_rets

    tracking_error = float(diff_rets.std(ddof=0) * np.sqrt(252)) if len(diff_rets) > 1 else 0.0
    model_twr = float(m.iloc[-1] / m.iloc[0] - 1)
    actual_twr = float(a.iloc[-1] / a.iloc[0] - 1)
    strategy_gap = model_twr - actual_twr

    return {
        "tracking_error_annual": tracking_error,
        "model_twr": model_twr,
        "actual_twr": actual_twr,
        "strategy_gap": strategy_gap,
        "information_ratio": (model_rets.mean() / diff_rets.std() if diff_rets.std() > 0 else 0.0),
    }
