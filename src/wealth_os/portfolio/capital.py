"""Capital Manager — deployment, contributions, dual cash pools, yield.

Implements:
- Phased initial deployment (avoid deploying all capital at once)
- Ongoing contribution handling (shares-based, not NAV-contaminating)
- Dual CNY/USD cash pools with independent yields
- New capital prioritises underweight assets
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd


class DeploymentState(StrEnum):
    DEPLOYING = "deploying"
    FULLY_DEPLOYED = "fully_deployed"
    PAUSED = "paused"


@dataclass
class CashPool:
    """Single-currency cash pool with yield accrual."""

    currency: str
    balance: float = 0.0
    annual_yield: float = 0.02  # 2% default
    _accrued: float = 0.0

    def accrue(self, days: float, trading_days_per_year: int = 252) -> float:
        daily_rate = (1 + self.annual_yield) ** (1 / trading_days_per_year) - 1
        interest = float(self.balance * daily_rate * days)
        self.balance += interest
        self._accrued += interest
        return interest

    def deposit(self, amount: float) -> None:
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        self.balance = max(0.0, self.balance - amount)

    def reset_accrued(self) -> float:
        total = self._accrued
        self._accrued = 0.0
        return total


@dataclass
class CapitalManager:
    """Manages total portfolio capital, deployment, and cash pools.

    All external contributions are handled via share issuance —
    they never contaminate unit-NAV or strategy returns.
    """

    total_capital: float = 0.0
    deployed_capital: float = 0.0
    initial_capital: float = 0.0
    deployment_target: float = 0.65  # initial deployment ratio
    min_deployment_step: float = 0.05  # minimum step per deployment day

    state: DeploymentState = DeploymentState.DEPLOYING
    deployment_days_elapsed: int = 0
    deployment_interval_days: int = 20  # days between deployment steps

    cash_pools: dict[str, CashPool] = field(default_factory=dict)
    total_contributions: float = 0.0
    units_outstanding: float = 1000.0  # initial fund units

    def __post_init__(self) -> None:
        if not self.cash_pools:
            self.cash_pools = {
                "CNY": CashPool(currency="CNY", balance=self.total_capital),
            }

    # ── Deployment ────────────────────────────────────────────────

    def step_deployment(self) -> float:
        """Return amount to deploy this step (0 if fully deployed)."""
        if self.state != DeploymentState.DEPLOYING:
            return 0.0

        self.deployment_days_elapsed += 1

        if self.deployment_days_elapsed % self.deployment_interval_days != 0:
            return 0.0

        undeployed = self.total_capital - self.deployed_capital
        target_deployed = self.total_capital * self.deployment_target

        if self.deployed_capital >= target_deployed:
            self.state = DeploymentState.FULLY_DEPLOYED
            return 0.0

        step = max(
            target_deployed - self.deployed_capital,
            self.total_capital * self.min_deployment_step,
        )
        step = min(step, undeployed)

        self.deployed_capital += step
        for pool in self.cash_pools.values():
            pool.withdraw(step / len(self.cash_pools))
        return step

    # ── Contributions ─────────────────────────────────────────────

    def record_contribution(
        self,
        amount: float,
        currency: str = "CNY",
        unit_nav: float = 1.0,
    ) -> float:
        """Handle external cash inflow via share issuance.

        Returns the number of new units issued.
        """
        self.total_contributions += amount
        self.total_capital += amount
        new_units = amount / max(unit_nav, 1e-12)
        self.units_outstanding += new_units

        pool = self.cash_pools.get(currency)
        if pool is not None:
            pool.deposit(amount)
        else:
            self.cash_pools[currency] = CashPool(currency=currency, balance=amount)

        return new_units

    def record_withdrawal(
        self, amount: float, currency: str = "CNY", unit_nav: float = 1.0
    ) -> float:
        """Handle withdrawal via share redemption."""
        amount = min(amount, self._total_balance())
        self.total_contributions -= amount
        self.total_capital -= amount
        redeemed_units = amount / max(unit_nav, 1e-12)
        self.units_outstanding = max(0.0, self.units_outstanding - redeemed_units)

        pool = self.cash_pools.get(currency)
        if pool is not None:
            pool.withdraw(amount)
        return redeemed_units

    # ── Cash management ───────────────────────────────────────────

    def accrue_cash(self, days: float = 1.0) -> float:
        """Accrue interest on all cash pools."""
        total = 0.0
        for pool in self.cash_pools.values():
            total += pool.accrue(days)
        return total

    def total_cash_balance(self) -> float:
        return sum(p.balance for p in self.cash_pools.values())

    def available_to_deploy(self) -> float:
        """Cash available to deploy into risk assets."""
        min_cash_ratio = 0.05
        total = self._total_balance()
        min_cash = total * min_cash_ratio
        available = self.total_cash_balance() - min_cash
        return max(0.0, available)

    def allocate_new_capital_to_underweight(
        self,
        target_weights: pd.Series,
        current_weights: pd.Series,
        available: float,
    ) -> pd.Series:
        """Distribute available capital to most underweight assets."""
        if available <= 0:
            return target_weights

        gap = target_weights - current_weights
        underweight = gap[gap > 0]
        if underweight.empty:
            return target_weights

        total_gap = underweight.sum()
        if total_gap <= 0:
            return target_weights

        allocation = underweight / total_gap * available
        new_targets = current_weights + allocation
        new_targets = new_targets / new_targets.sum()
        return new_targets

    # ── State ─────────────────────────────────────────────────────

    def _total_balance(self) -> float:
        return self.total_cash_balance() + self.deployed_capital

    def summary(self) -> dict:
        return {
            "total_capital": self.total_capital,
            "deployed_capital": self.deployed_capital,
            "cash_balance": self.total_cash_balance(),
            "total_contributions": self.total_contributions,
            "units_outstanding": self.units_outstanding,
            "state": str(self.state),
            "deployment_target": self.deployment_target,
            "cash_pools": {c: p.balance for c, p in self.cash_pools.items()},
        }
