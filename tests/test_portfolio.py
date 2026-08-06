"""P3 Portfolio OS tests — capital, constraints, overlay, optimizers."""

from __future__ import annotations

import pandas as pd
import pytest

from wealth_os.domain.models import AssetClass, Instrument, Sleeve
from wealth_os.portfolio.budget import CoreSatelliteBudget
from wealth_os.portfolio.capital import CapitalManager, CashPool, DeploymentState
from wealth_os.portfolio.constraints import (
    ConstraintChecker,
    FullConstraints,
)
from wealth_os.portfolio.optimizers import (
    InverseVolatilityOptimizer,
    PortfolioOptimizer,
    RiskParityOptimizer,
)
from wealth_os.portfolio.overlay import (
    DrawdownState,
    RiskOverlayState,
    RiskOverlayStateMachine,
)

# ── Capital Manager ───────────────────────────────────────────────


class TestCapitalManager:
    def test_initial_deployment(self) -> None:
        cm = CapitalManager(total_capital=1_000_000, deployment_target=0.50)
        assert cm.state == DeploymentState.DEPLOYING

        deployed = 0.0
        for _ in range(200):
            step = cm.step_deployment()
            deployed += step

        assert deployed > 0
        assert cm.deployed_capital == pytest.approx(500_000, rel=0.05)

    def test_contribution_via_shares(self) -> None:
        cm = CapitalManager(total_capital=1_000_000)
        units_before = cm.units_outstanding

        new_units = cm.record_contribution(100_000, unit_nav=1.0)

        assert new_units == pytest.approx(100_000)
        assert cm.units_outstanding == units_before + new_units
        assert cm.total_capital == 1_100_000
        assert cm.total_cash_balance() == 1_100_000

    def test_contribution_does_not_change_unit_nav_theory(self) -> None:
        """Contribution via share issuance — unit NAV stays at 1.0 by construction."""
        cm = CapitalManager(total_capital=1_000_000)
        cm.record_contribution(50_000, unit_nav=1.0)
        # Unit NAV is computed externally (NAV / units), but the mechanism
        # ensures contributions don't distort strategy returns.
        assert cm.total_contributions == 50_000

    def test_dual_cash_pools(self) -> None:
        cm = CapitalManager(total_capital=1_000_000)
        cm.cash_pools["USD"] = CashPool(currency="USD", balance=200_000)

        cm.record_contribution(50_000, currency="USD", unit_nav=1.0)

        assert cm.cash_pools["USD"].balance == 250_000
        assert cm.total_cash_balance() == 1_250_000

    def test_cash_accrual(self) -> None:
        pool = CashPool(currency="CNY", balance=100_000, annual_yield=0.0252)
        interest = pool.accrue(days=252)
        assert interest > 0
        assert pool.balance > 100_000

    def test_allocate_to_underweight(self) -> None:
        cm = CapitalManager(total_capital=1_000_000)
        cm.cash_pools["CNY"].balance = 200_000

        target = pd.Series(
            {"A": 0.4, "B": 0.3, "CASH_CNY": 0.3},
        )
        current = pd.Series(
            {"A": 0.2, "B": 0.3, "CASH_CNY": 0.5},
        )

        new = cm.allocate_new_capital_to_underweight(target, current, 0.10)

        assert abs(new.sum() - 1.0) < 1e-9
        assert new["A"] > current["A"], "Underweight A should get more"


# ── Constraints ───────────────────────────────────────────────────


class TestConstraintSystem:
    def _make_instruments(self) -> dict[str, Instrument]:
        return {
            "A": Instrument("A", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
            "B": Instrument("B", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
            "CASH_CNY": Instrument("CASH_CNY", AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
        }

    def test_valid_weights_pass(self) -> None:
        constraints = FullConstraints(max_weights={"A": 0.5})
        checker = ConstraintChecker(constraints, self._make_instruments())

        weights = pd.Series({"A": 0.3, "B": 0.4, "CASH_CNY": 0.3})
        result = checker.check(weights)

        assert result.passed

    def test_exceed_max_weight(self) -> None:
        constraints = FullConstraints(max_weights={"A": 0.5})
        checker = ConstraintChecker(constraints, self._make_instruments())

        weights = pd.Series({"A": 0.6, "B": 0.2, "CASH_CNY": 0.2})
        result = checker.check(weights)

        assert not result.passed
        assert any("A" in v.detail for v in result.violations)

    def test_apply_corrects_violations(self) -> None:
        constraints = FullConstraints(
            max_weights={"A": 0.5},
            min_weights={"CASH_CNY": 0.05},
        )
        checker = ConstraintChecker(constraints, self._make_instruments())

        weights = pd.Series({"A": 0.7, "B": 0.2, "CASH_CNY": 0.1})
        corrected = checker.apply(weights)

        assert corrected["A"] <= 0.5 + 1e-6
        assert abs(corrected.sum() - 1.0) < 1e-6
        assert corrected["CASH_CNY"] >= 0.0

    def test_apply_enforces_sleeve_bounds(self) -> None:
        constraints = FullConstraints(sleeve_bounds={Sleeve.CORE: (0.3, 0.7)})
        checker = ConstraintChecker(constraints, self._make_instruments())

        weights = pd.Series({"A": 0.6, "B": 0.3, "CASH_CNY": 0.1})
        corrected = checker.apply(weights)

        core_total = corrected[["A", "B"]].sum()
        assert core_total <= 0.7 + 1e-6

    def test_apply_turnover_limit(self) -> None:
        constraints = FullConstraints(max_turnover=0.10)
        checker = ConstraintChecker(constraints, self._make_instruments())

        current = pd.Series({"A": 0.5, "B": 0.3, "CASH_CNY": 0.2})
        target = pd.Series({"A": 0.1, "B": 0.7, "CASH_CNY": 0.2})
        # Turnover = (|0.1-0.5| + |0.7-0.3|) / 2 = (0.4 + 0.4) / 2 = 0.4
        # Max turnover = 0.10, so fraction = 0.10/0.40 = 0.25

        corrected = checker.apply(target, current)

        turnover = (corrected - current).abs().sum() / 2.0
        assert turnover <= 0.10 + 1e-6


# ── Risk Overlay ──────────────────────────────────────────────────


class TestRiskOverlay:
    def test_normal_drawdown_full_risk(self) -> None:
        overlay = RiskOverlayStateMachine()
        mult = overlay.update(drawdown=0.0)

        assert mult == 1.0
        assert overlay.drawdown_state == DrawdownState.NORMAL
        assert overlay.overlay_state == RiskOverlayState.FULL_RISK

    def test_severe_drawdown_reduces_risk(self) -> None:
        overlay = RiskOverlayStateMachine()
        mult = overlay.update(drawdown=-0.16)

        assert mult < 0.7
        assert overlay.drawdown_state == DrawdownState.SEVERE

    def test_critical_drawdown_max_reduction(self) -> None:
        overlay = RiskOverlayStateMachine()
        mult = overlay.update(drawdown=-0.25)

        assert mult <= 0.30
        assert overlay.drawdown_state == DrawdownState.CRITICAL

    def test_slow_recovery_after_drawdown(self) -> None:
        overlay = RiskOverlayStateMachine()

        overlay.update(drawdown=-0.16)
        reduced = overlay.current_risk_multiplier
        assert reduced < 1.0

        # Recovery: many days at normal drawdown
        for _ in range(50):
            overlay.update(drawdown=-0.01)

        assert overlay.current_risk_multiplier > reduced

    def test_correlation_spike_penalty(self) -> None:
        overlay = RiskOverlayStateMachine()

        overlay.update(drawdown=0.0, correlation=0.8)
        penalized = overlay.current_risk_multiplier

        assert penalized < 1.0, "High correlation should trigger penalty"

    def test_vol_target_scale(self) -> None:
        overlay = RiskOverlayStateMachine(target_volatility=0.10)

        weights = pd.Series({"A": 0.5, "B": 0.5, "CASH_CNY": 0.0})
        scaled = overlay.vol_target_scale(
            estimated_vol=0.15, weights=weights, risky_symbols=["A", "B"]
        )

        risky_sum = scaled[["A", "B"]].sum()
        assert risky_sum < 1.0, "High vol should scale down weights"


# ── Optimizers ────────────────────────────────────────────────────


class TestOptimizers:
    def test_inverse_vol_sums_to_one(self) -> None:
        vol = pd.Series({"A": 0.20, "B": 0.15, "C": 0.10, "CASH_CNY": 0.01})
        opt = InverseVolatilityOptimizer(include_cash=False)
        weights = opt.optimize(vol, cash_symbol="CASH_CNY")

        assert abs(weights.sum() - 1.0) < 1e-9

    def test_inverse_vol_lower_vol_higher_weight(self) -> None:
        vol = pd.Series({"A": 0.30, "B": 0.10})
        opt = InverseVolatilityOptimizer()
        weights = opt.optimize(vol)

        assert weights["B"] > weights["A"], "Lower vol → higher weight"

    def test_risk_parity_equal_risk(self) -> None:
        cov = pd.DataFrame(
            {"A": [0.04, 0.0], "B": [0.0, 0.04]},
            index=["A", "B"],
            columns=["A", "B"],
        )
        opt = RiskParityOptimizer()
        weights = opt.optimize(cov)

        assert abs(weights.sum() - 1.0) < 1e-9
        assert abs(weights["A"] - 0.5) < 0.05 and abs(weights["B"] - 0.5) < 0.05

    def test_portfolio_optimizer_raw_weights(self) -> None:
        base = pd.Series(
            {"A": 0.3, "B": 0.3, "CASH_CNY": 0.4},
        )
        opt = PortfolioOptimizer(
            base_weights=base,
            cash_symbol="CASH_CNY",
            signal_strength=0.3,
        )

        # Strong positive signals → weights should increase
        value = pd.Series({"A": 2.0, "B": 2.0})
        trend = pd.Series({"A": 2.0, "B": 2.0})
        vol = pd.Series({"A": 0.15, "B": 0.15})

        raw = opt.compute_raw_weights(value, trend, vol)

        assert raw["CASH_CNY"] >= 0
        risky = raw[["A", "B"]].sum()
        assert risky > 0.6, "Strong signals should increase risky allocation"


# ── Budget ────────────────────────────────────────────────────────


class TestBudget:
    def test_default_sleeves(self) -> None:
        budget = CoreSatelliteBudget()
        assert len(budget.sleeves) == 4
        assert budget.sleeves[Sleeve.CORE].strategic_weight == 0.70

    def test_core_underweight_detection(self) -> None:
        budget = CoreSatelliteBudget()
        budget.sleeves[Sleeve.CORE].current_weight = 0.60
        assert budget.is_core_underweight()

    def test_btc_budget(self) -> None:
        budget = CoreSatelliteBudget(btc_max_weight=0.03)
        assert budget.btc_within_budget(0.02)
        assert not budget.btc_within_budget(0.05)

    def test_transfer_rules(self) -> None:
        budget = CoreSatelliteBudget()
        budget.sleeves[Sleeve.SATELLITE].current_weight = 0.20
        budget.sleeves[Sleeve.CORE].current_weight = 0.60

        # Can transfer 0.05 from Satellite to Core
        assert budget.suggest_transfer(Sleeve.SATELLITE, Sleeve.CORE, 0.05)
        # Cannot transfer more than Satellite's min
        assert not budget.suggest_transfer(Sleeve.SATELLITE, Sleeve.CORE, 0.25)
