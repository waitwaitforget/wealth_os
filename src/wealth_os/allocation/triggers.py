from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from wealth_os.domain.models import TriggerConfig


@dataclass
class TriggerDecision:
    should_rebalance: bool
    reasons: tuple[str, ...]


class RebalanceTriggerEngine:
    def __init__(self, config: TriggerConfig):
        self.config = config
        self._last_rebalance: pd.Timestamp | None = None
        self._previous_signal_bucket: pd.Series | None = None
        self._previous_drawdown_level: int = 0

    def evaluate(
        self,
        date: pd.Timestamp,
        actual_weights: pd.Series,
        target_weights: pd.Series,
        composite_signal: pd.Series,
        portfolio_volatility: float,
        target_volatility: float,
        drawdown: float,
        external_cash_flow: float = 0.0,
    ) -> TriggerDecision:
        reasons: list[str] = []
        risk_override = False

        for symbol in target_weights.index:
            threshold = self.config.weight_drift.get(symbol, self.config.default_weight_drift)
            if abs(float(actual_weights.get(symbol, 0.0) - target_weights[symbol])) >= threshold:
                reasons.append(f"weight_drift:{symbol}")

        buckets = np.floor(composite_signal / self.config.signal_step).astype("Int64")
        if self._previous_signal_bucket is not None:
            changed = buckets.ne(self._previous_signal_bucket.reindex(buckets.index)).fillna(False)
            reasons.extend(f"signal_bucket:{s}" for s in changed[changed].index)
        self._previous_signal_bucket = buckets

        if portfolio_volatility > target_volatility * self.config.volatility_multiple:
            reasons.append("volatility_breach")
            risk_override = True

        level = sum(drawdown <= threshold for threshold in self.config.drawdown_levels)
        if level > self._previous_drawdown_level:
            reasons.append(f"drawdown_level:{level}")
            risk_override = True
        self._previous_drawdown_level = level

        if external_cash_flow > 0:
            reasons.append("cash_flow")

        cooldown_ok = (
            self._last_rebalance is None
            or (date - self._last_rebalance).days >= self.config.cooldown_days
        )
        should = bool(reasons) and (cooldown_ok or risk_override)
        if should:
            self._last_rebalance = date
        return TriggerDecision(should, tuple(dict.fromkeys(reasons)))
