"""VTR Allocation Policy — thin wrapper over PortfolioOptimizer + ConstraintChecker.

Delegates signal combination and risk scaling to PortfolioOptimizer
and constraint enforcement to ConstraintChecker.  Maintains backward
compatible interface.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from wealth_os.domain.models import Instrument, PortfolioConstraints
from wealth_os.portfolio.constraints import ConstraintChecker, FullConstraints
from wealth_os.portfolio.optimizers import PortfolioOptimizer


def _convert_constraints(
    old: PortfolioConstraints,
    instruments: dict[str, Instrument],
) -> FullConstraints:
    return FullConstraints(
        min_weights=dict(old.min_weights),
        max_weights=dict(old.max_weights),
        sleeve_bounds={str(k): v for k, v in old.sleeve_bounds.items()},
        currency_bounds=dict(old.currency_bounds),
        max_turnover=old.max_turnover,
        allow_leverage=old.allow_leverage,
    )


@dataclass
class VTRAllocationPolicy:
    instruments: Mapping[str, Instrument]
    base_weights: pd.Series
    constraints: PortfolioConstraints
    cash_symbol: str
    value_weight: float = 0.40
    trend_weight: float = 0.40
    inverse_vol_weight: float = 0.20
    signal_strength: float = 0.30
    target_volatility: float = 0.10

    def __post_init__(self) -> None:
        inst_dict = dict(self.instruments)
        full_c = _convert_constraints(self.constraints, inst_dict)
        self._optimizer = PortfolioOptimizer(
            base_weights=self.base_weights,
            cash_symbol=self.cash_symbol,
            value_weight=self.value_weight,
            trend_weight=self.trend_weight,
            risk_weight=self.inverse_vol_weight,
            signal_strength=self.signal_strength,
            target_volatility=self.target_volatility,
        )
        self._checker = ConstraintChecker(full_c, inst_dict)

    def generate_target_weights(
        self,
        date: pd.Timestamp,
        current_weights: pd.Series,
        signals: pd.DataFrame,
        volatility: pd.Series,
    ) -> pd.Series:
        value = signals.loc["value"] if "value" in signals.index else pd.Series(dtype=float)
        trend = signals.loc["trend"] if "trend" in signals.index else pd.Series(dtype=float)

        raw = self._optimizer.compute_raw_weights(value, trend, volatility)
        return self._checker.apply(raw, current_weights)
