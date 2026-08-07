"""Risk Overlay state machine — drawdown-driven risk scaling.

Implements:
- Target volatility scaling
- Drawdown state machine (5 levels)
- Fast risk reduction, slow recovery (asymmetric)
- Correlation shock detection
- Risk budget enforcement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

import pandas as pd


class DrawdownState(StrEnum):
    NORMAL = "normal"  # < -5%
    NOTABLE = "notable"  # -5% to -10%
    SIGNIFICANT = "significant"  # -10% to -15%
    SEVERE = "severe"  # -15% to -20%
    CRITICAL = "critical"  # > -20%


class RiskOverlayState(StrEnum):
    FULL_RISK = "full_risk"  # 100% of target risk
    REDUCING = "reducing"  # actively lowering risk
    REDUCED = "reduced"  # operating at lower risk
    RECOVERING = "recovering"  # slowly raising risk back
    PAUSED = "paused"  # no risk-taking


@dataclass
class RiskOverlayStateMachine:
    """Drawdown-driven asymmetric risk scaling state machine.

    Risk reduction is fast (immediate multiplier changes).
    Risk recovery is slow (gradual, stepped increases).
    """

    target_volatility: float = 0.10
    max_volatility: float = 0.20
    current_risk_multiplier: float = 1.0

    drawdown_state: DrawdownState = DrawdownState.NORMAL
    overlay_state: RiskOverlayState = RiskOverlayState.FULL_RISK

    # Recovery parameters
    recovery_step: float = 0.05  # risk multiplier increment per step
    recovery_interval_days: int = 5  # days between recovery steps
    recovery_cooldown: int = 0  # remaining cooldown days
    recovery_trigger_dd: float = -0.03  # DD must be above this to start recovery

    # History
    state_history: list[tuple[str, float]] = field(default_factory=list)
    _previous_drawdown: float = 0.0
    _correlation_spike_detected: bool = False

    # ── Drawdown thresholds ───────────────────────────────────────

    DD_THRESHOLDS: ClassVar[list[tuple[float, DrawdownState]]] = [
        (-0.20, DrawdownState.CRITICAL),
        (-0.15, DrawdownState.SEVERE),
        (-0.10, DrawdownState.SIGNIFICANT),
        (-0.05, DrawdownState.NOTABLE),
        (0.0, DrawdownState.NORMAL),
    ]

    RISK_MULTIPLIERS: ClassVar[dict[DrawdownState, float]] = {
        DrawdownState.NORMAL: 1.0,
        DrawdownState.NOTABLE: 0.70,
        DrawdownState.SIGNIFICANT: 0.50,
        DrawdownState.SEVERE: 0.30,
        DrawdownState.CRITICAL: 0.05,  # nearly all cash
    }

    # ── Update ────────────────────────────────────────────────────

    def update(
        self,
        drawdown: float,
        correlation: float | None = None,
        portfolio_vol: float | None = None,
    ) -> float:
        """Process a new drawdown observation and return the risk multiplier.

        Args:
            drawdown: Current portfolio drawdown (negative = loss).
            correlation: Average pairwise correlation (optional).
            portfolio_vol: Current realised portfolio volatility (optional).

        Returns:
            Risk multiplier to apply to target weights (0.0–1.0).
        """
        dd_is_worsening = drawdown < self._previous_drawdown
        self._previous_drawdown = drawdown

        # Step 1: Classify drawdown
        new_dd_state = DrawdownState.NORMAL
        for threshold, state in self.DD_THRESHOLDS:
            if drawdown <= threshold:
                new_dd_state = state
                break
        self.drawdown_state = new_dd_state

        # Step 2: Check correlation spike
        if correlation is not None and correlation > 0.7:
            self._correlation_spike_detected = True
        elif correlation is not None and correlation < 0.5:
            self._correlation_spike_detected = False

        # Step 3: Determine overlay state and risk multiplier
        if dd_is_worsening and new_dd_state != DrawdownState.NORMAL:
            self.overlay_state = RiskOverlayState.REDUCING
            target_mult = self.RISK_MULTIPLIERS[new_dd_state]
            self.current_risk_multiplier = min(self.current_risk_multiplier, target_mult)
            self.recovery_cooldown = 20  # wait before recovering
        elif (
            new_dd_state == DrawdownState.NORMAL
            and self.overlay_state != RiskOverlayState.FULL_RISK
        ):
            if self.recovery_cooldown > 0:
                self.recovery_cooldown -= 1
                self.overlay_state = RiskOverlayState.REDUCED
            else:
                self.overlay_state = RiskOverlayState.RECOVERING
                target = self.RISK_MULTIPLIERS[DrawdownState.NORMAL]
                self.current_risk_multiplier = min(
                    target,
                    self.current_risk_multiplier + self.recovery_step,
                )
                if self.current_risk_multiplier >= 0.95:
                    self.overlay_state = RiskOverlayState.FULL_RISK
                    self.current_risk_multiplier = 1.0
        else:
            self.overlay_state = RiskOverlayState.FULL_RISK

        # Step 4: Correlation penalty
        if self._correlation_spike_detected:
            self.current_risk_multiplier *= 0.85

        # Step 5: Clamp
        self.current_risk_multiplier = max(0.1, min(1.0, self.current_risk_multiplier))

        self.state_history.append(
            (
                str(self.overlay_state),
                self.current_risk_multiplier,
            )
        )
        return self.current_risk_multiplier

    # ── Volatility target scaling ────────────────────────────────

    def vol_target_scale(
        self,
        estimated_vol: float,
        weights: pd.Series,
        risky_symbols: list[str],
    ) -> pd.Series:
        """Scale weights to meet target volatility.

        Also applies the drawdown risk multiplier.
        """
        if estimated_vol <= 0:
            return weights

        scale = min(1.0, self.target_volatility / estimated_vol)
        scale *= self.current_risk_multiplier
        scale = min(scale, self.max_volatility / max(estimated_vol, 0.001))

        out = weights.copy()
        risky_weights = out[risky_symbols] * scale
        out.loc[risky_symbols] = risky_weights
        return out

    def summary(self) -> dict:
        return {
            "overlay_state": str(self.overlay_state),
            "drawdown_state": str(self.drawdown_state),
            "risk_multiplier": self.current_risk_multiplier,
            "target_vol": self.target_volatility,
            "correlation_spike": self._correlation_spike_detected,
            "recovery_cooldown": self.recovery_cooldown,
        }
