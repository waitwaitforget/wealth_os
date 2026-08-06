"""Core / Satellite budget — dynamic capital allocation between sleeves.

Implements:
- Strategic central weights with allowable ranges
- Core ↔ Satellite capital flow rules
- BTC independent risk budget
- Risk contribution per sleeve
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wealth_os.domain.models import Instrument, Sleeve


@dataclass
class SleeveBudget:
    """Capital budget for a single investment sleeve."""

    sleeve: Sleeve
    strategic_weight: float  # central target
    min_weight: float = 0.0
    max_weight: float = 1.0
    current_weight: float = 0.0
    risk_contribution: float = 0.0  # fraction of total portfolio risk

    @property
    def within_range(self) -> bool:
        return self.min_weight <= self.current_weight <= self.max_weight

    @property
    def deviation(self) -> float:
        """Signed distance from strategic weight."""
        return self.current_weight - self.strategic_weight


@dataclass
class CoreSatelliteBudget:
    """Manages dynamic capital allocation across Core, Satellite, Alternative, Cash.

    Rules:
    - Core weight cannot exceed its upper bound without manual approval
    - Satellite funds can be redirected to Core if Core is underweight AND
      Satellite signals are weak
    - BTC (Alternative) has its own independent risk budget
    - Cash is the residual
    """

    sleeves: dict[Sleeve, SleeveBudget] = field(default_factory=dict)

    # BTC-specific
    btc_max_weight: float = 0.05
    btc_risk_budget: float = 0.10  # max % of total portfolio risk from BTC

    def __post_init__(self) -> None:
        if not self.sleeves:
            self._set_defaults()

    def _set_defaults(self) -> None:
        self.sleeves = {
            Sleeve.CORE: SleeveBudget(
                sleeve=Sleeve.CORE,
                strategic_weight=0.70,
                min_weight=0.45,
                max_weight=0.90,
            ),
            Sleeve.SATELLITE: SleeveBudget(
                sleeve=Sleeve.SATELLITE,
                strategic_weight=0.15,
                min_weight=0.0,
                max_weight=0.30,
            ),
            Sleeve.ALTERNATIVE: SleeveBudget(
                sleeve=Sleeve.ALTERNATIVE,
                strategic_weight=0.03,
                min_weight=0.0,
                max_weight=0.10,
            ),
            Sleeve.CASH: SleeveBudget(
                sleeve=Sleeve.CASH,
                strategic_weight=0.12,
                min_weight=0.05,
                max_weight=0.50,
            ),
        }

    # ── Update from current portfolio ─────────────────────────────

    def update_weights(
        self,
        weights: pd.Series,
        instruments: dict[str, Instrument],
    ) -> None:
        """Recalculate sleeve weights from position weights."""
        totals: dict[Sleeve, float] = dict.fromkeys(Sleeve, 0.0)
        for sym, w in weights.items():
            inst = instruments.get(sym)
            if inst is not None:
                totals[inst.sleeve] += w

        for sleeve, budget in self.sleeves.items():
            budget.current_weight = totals.get(sleeve, 0.0)

    def update_risk_contributions(
        self,
        weights: pd.Series,
        covariance: pd.DataFrame,
        instruments: dict[str, Instrument],
    ) -> None:
        """Estimate risk contribution per sleeve (approximate)."""
        portfolio_var = float(weights @ covariance.reindex(weights.index).fillna(0.0) @ weights)
        if portfolio_var <= 0:
            return

        sleeve_mcr: dict[Sleeve, float] = dict.fromkeys(Sleeve, 0.0)
        for sym, w in weights.items():
            inst = instruments.get(sym)
            if inst is None or w == 0:
                continue
            cov_row = covariance.reindex([sym]).fillna(0.0).values.flatten()
            mcr_i = float(np.dot(cov_row, weights)) / portfolio_var
            sleeve_mcr[inst.sleeve] += abs(w * mcr_i)

        for sleeve, budget in self.sleeves.items():
            budget.risk_contribution = sleeve_mcr.get(sleeve, 0.0)

    # ── Budget adjustments ────────────────────────────────────────

    def suggest_transfer(
        self,
        from_sleeve: Sleeve,
        to_sleeve: Sleeve,
        amount: float,
    ) -> bool:
        """Check if a capital transfer between sleeves is allowed.

        Returns True if the transfer does not violate bounds.
        """
        from_budget = self.sleeves[from_sleeve]
        to_budget = self.sleeves[to_sleeve]

        new_from = from_budget.current_weight - amount
        new_to = to_budget.current_weight + amount

        return new_from >= from_budget.min_weight and new_to <= to_budget.max_weight

    def is_core_underweight(self) -> bool:
        core = self.sleeves[Sleeve.CORE]
        return core.current_weight < core.strategic_weight - 0.05

    def can_reduce_satellite(self) -> bool:
        sat = self.sleeves[Sleeve.SATELLITE]
        return sat.current_weight > sat.min_weight + 0.02

    def btc_within_budget(self, btc_weight: float) -> bool:
        return btc_weight <= self.btc_max_weight

    # ── Summary ───────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            str(s): {
                "strategic": b.strategic_weight,
                "current": b.current_weight,
                "range": [b.min_weight, b.max_weight],
                "risk_contribution": b.risk_contribution,
                "deviation": b.deviation,
            }
            for s, b in self.sleeves.items()
        }
