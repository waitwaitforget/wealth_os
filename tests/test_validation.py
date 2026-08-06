"""P4 Validation OS tests — reconciliation, statistical, governance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wealth_os.domain.models import BacktestResult
from wealth_os.validation.governance import (
    ShadowPortfolio,
    StrategyLifecycle,
    StrategyState,
    analyze_model_vs_actual_deviation,
)
from wealth_os.validation.reconciliation import (
    reconcile_backtests,
    validate_capital_conservation,
)
from wealth_os.validation.statistical import (
    bootstrap_metrics,
)

# ── Reconciliation ────────────────────────────────────────────────


def _make_result(nav_vals: list[float], **kwargs) -> BacktestResult:
    idx = pd.date_range("2024-01-01", periods=len(nav_vals), freq="B")
    nav = pd.Series(nav_vals, index=idx)
    return BacktestResult(
        nav=nav,
        unit_nav=nav / nav.iloc[0],
        units=pd.Series(1000.0, index=idx),
        cash=pd.Series(100.0, index=idx),
        positions_value=pd.DataFrame({"A": nav - 100}, index=idx),
        actual_weights=pd.DataFrame({"A": [0.8] * len(idx), "CASH": [0.2] * len(idx)}, index=idx),
        target_weights=pd.DataFrame({"A": [0.8] * len(idx), "CASH": [0.2] * len(idx)}, index=idx),
        external_cash_flows=pd.Series(0.0, index=idx),
        transaction_costs=pd.Series(0.0, index=idx),
        turnover=pd.Series(0.0, index=idx),
        orders=pd.DataFrame(),
    )


class TestReconciliation:
    def test_identical_engines_pass(self) -> None:
        n = 20
        vals = list(range(1000, 1000 + n * 10, 10))
        a = _make_result(vals)
        b = _make_result(vals)

        report = reconcile_backtests(a, b)
        assert report.passed
        assert report.nav_correlation == pytest.approx(1.0)

    def test_divergent_engines_fail(self) -> None:
        a = _make_result([1000, 1010, 1020, 1030, 1040])
        b = _make_result([1000, 1020, 1040, 1060, 1080])

        report = reconcile_backtests(a, b, nav_tolerance=1e-4)
        assert not report.passed

    def test_capital_conservation_passes(self) -> None:
        idx = pd.date_range("2024-01-01", periods=10, freq="B")
        nav = pd.Series([1000.0] * 10, index=idx)
        result = BacktestResult(
            nav=nav,
            unit_nav=nav / 1000,
            units=pd.Series([1000.0] * 10, index=idx),
            cash=pd.Series([200.0] * 10, index=idx),
            positions_value=pd.DataFrame({"A": [800.0] * 10}, index=idx),
            actual_weights=pd.DataFrame({"A": [0.8] * 10, "CASH": [0.2] * 10}, index=idx),
            target_weights=pd.DataFrame({"A": [0.8] * 10, "CASH": [0.2] * 10}, index=idx),
            external_cash_flows=pd.Series(0.0, index=idx),
            transaction_costs=pd.Series(0.0, index=idx),
            turnover=pd.Series(0.0, index=idx),
            orders=pd.DataFrame(),
        )
        issues = validate_capital_conservation(result)
        assert len(issues) == 0

    def test_negative_cash_detected(self) -> None:
        idx = pd.date_range("2024-01-01", periods=5, freq="B")
        nav = pd.Series([1000.0] * 5, index=idx)
        result = BacktestResult(
            nav=nav,
            unit_nav=nav / 1000,
            units=pd.Series([1000.0] * 5, index=idx),
            cash=pd.Series([-10.0, 0.0, 0.0, 0.0, 0.0], index=idx),
            positions_value=pd.DataFrame({"A": [1010.0] * 5}, index=idx),
            actual_weights=pd.DataFrame({"A": [1.0] * 5, "CASH": [0.0] * 5}, index=idx),
            target_weights=pd.DataFrame({"A": [1.0] * 5, "CASH": [0.0] * 5}, index=idx),
            external_cash_flows=pd.Series(0.0, index=idx),
            transaction_costs=pd.Series(0.0, index=idx),
            turnover=pd.Series(0.0, index=idx),
            orders=pd.DataFrame(),
        )
        issues = validate_capital_conservation(result)
        assert len(issues) > 0


# ── Statistical ───────────────────────────────────────────────────


class TestBootstrap:
    def test_bootstrap_returns_confidence_intervals(self) -> None:
        idx = pd.date_range("2020-01-01", periods=500, freq="B")
        rng = np.random.RandomState(42)
        nav = pd.Series(
            1000 * np.exp(rng.standard_normal(500).cumsum() * 0.01),
            index=idx,
        )
        result = bootstrap_metrics(nav, n_bootstrap=100)
        assert "sharpe" in result
        assert result["sharpe"]["ci_lower"] <= result["sharpe"]["ci_upper"]


# ── Governance ────────────────────────────────────────────────────


class TestStrategyLifecycle:
    def test_valid_transitions(self) -> None:
        lifecycle = StrategyLifecycle("test_strategy")

        assert lifecycle.can_transition(StrategyState.CANDIDATE)
        assert not lifecycle.can_transition(StrategyState.PRODUCTION)

        assert lifecycle.transition(StrategyState.CANDIDATE)
        assert lifecycle.current_state == StrategyState.CANDIDATE

    def test_transitions_recorded_in_history(self) -> None:
        lifecycle = StrategyLifecycle("test_strategy")
        lifecycle.transition(StrategyState.CANDIDATE, reason="backtest done")
        lifecycle.transition(StrategyState.SHADOW, reason="60 days shadow")

        assert len(lifecycle.history) == 2
        assert lifecycle.history[0].from_state == StrategyState.RESEARCH

    def test_force_transition_bypasses_rules(self) -> None:
        lifecycle = StrategyLifecycle("test_strategy")
        assert lifecycle.transition(StrategyState.PRODUCTION, reason="emergency", force=True)

    def test_retired_cannot_transition(self) -> None:
        lifecycle = StrategyLifecycle("test_strategy")
        lifecycle.transition(StrategyState.RETIRED, force=True)
        assert not lifecycle.can_transition(StrategyState.RESEARCH)

    def test_requirements_for_production(self) -> None:
        lifecycle = StrategyLifecycle("test_strategy")
        reqs = lifecycle.requirements_for(StrategyState.PRODUCTION)
        assert len(reqs) >= 2
        assert any("approval" in r.lower() for r in reqs)


class TestShadowPortfolio:
    def test_initial_state(self) -> None:
        shadow = ShadowPortfolio(strategy_id="test", initial_capital=1_000_000)
        assert shadow.cash == 1_000_000
        assert len(shadow.positions) == 0

    def test_record_snapshot(self) -> None:
        shadow = ShadowPortfolio(strategy_id="test")
        prices = pd.Series({"A": 100, "B": 200})

        nav = shadow.record_snapshot(pd.Timestamp("2024-01-01"), prices, cash=1_000_000)
        assert nav == 1_000_000
        assert len(shadow.nav_history) == 1

    def test_to_nav_series(self) -> None:
        shadow = ShadowPortfolio(strategy_id="test")
        prices = pd.Series({"A": 100})

        for i in range(10):
            shadow.record_snapshot(
                pd.Timestamp(f"2024-01-{i + 1:02d}"),
                prices,
                cash=1_000_000 + i * 100,
            )

        series = shadow.to_nav_series()
        assert len(series) == 10
        assert series.iloc[-1] > series.iloc[0]


class TestDeviationAnalysis:
    def test_identical_portfolios(self) -> None:
        idx = pd.date_range("2024-01-01", periods=100, freq="B")
        nav = pd.Series(1000 + np.linspace(0, 100, 100), index=idx)

        result = analyze_model_vs_actual_deviation(nav, nav)
        assert result["tracking_error_annual"] == pytest.approx(0.0, abs=0.01)
        assert result["strategy_gap"] == pytest.approx(0.0, abs=0.01)
