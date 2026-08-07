"""Strategy Validation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wealth_os.evaluation.engine import (
    compute_complexity,
    compute_deflated_sharpe,
    compute_parameter_robustness,
    compute_pbo,
    compute_rolling_metrics,
)
from wealth_os.evaluation.gates import GateEngine
from wealth_os.evaluation.models import (
    DrawdownMetrics,
    EfficiencyMetrics,
    OverfittingMetrics,
    PerformanceMetrics,
    RiskMetricsDTO,
    StrategyReport,
)
from wealth_os.strategy.core import (
    adaptive_core_tilt,
    risk_managed_core_weights,
    static_saa_weights,
)


class TestComplexity:
    def test_simple_strategy(self) -> None:
        score = compute_complexity()
        assert score == 0.0

    def test_complex_strategy(self) -> None:
        score = compute_complexity(n_params=5, n_signals=3, n_states=4, n_thresholds=6, annual_turnover=2.0, n_dependencies=3)
        assert score > 3.0
        assert score <= 10.0


class TestPBO:
    def test_low_overfitting(self) -> None:
        df = pd.DataFrame({"sharpe": np.random.RandomState(42).uniform(0.5, 1.0, 50)})
        pbo = compute_pbo(df, n_simulations=30)
        assert 0 <= pbo <= 1


class TestDeflatedSharpe:
    def test_multiple_trials_penalty(self) -> None:
        sr1 = compute_deflated_sharpe(1.0, n_trials=1)
        sr2 = compute_deflated_sharpe(1.0, n_trials=100)
        assert sr2 < sr1


class TestRollingMetrics:
    def test_rolling_1y(self) -> None:
        idx = pd.date_range("2018-01-01", periods=500, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.3, 500), index=idx)
        rolling = compute_rolling_metrics(nav, window_days=252)
        assert rolling.positive_ratio > 0.5


class TestParameterRobustness:
    def test_stable_strategy(self) -> None:
        results = {200: 0.8, 220: 0.78, 240: 0.79, 260: 0.77, 280: 0.75, 300: 0.73}
        surface = compute_parameter_robustness(results)
        assert surface.robustness_score >= 0.8


class TestGateEngine:
    def _make_report(self) -> StrategyReport:
        return StrategyReport(
            strategy_id="test",
            performance=PerformanceMetrics(twr=0.5, cagr=0.06),
            risk=RiskMetricsDTO(annualized_volatility=0.12),
            drawdown=DrawdownMetrics(max_drawdown=-0.15),
            efficiency=EfficiencyMetrics(sharpe=0.5, sortino=0.7, calmar=0.4),
            overfitting=OverfittingMetrics(pbo=0.05, deflated_sharpe=0.8, complexity_score=3.0),
        )

    def test_all_gates_pass(self) -> None:
        report = self._make_report()
        engine = GateEngine()
        results = engine.evaluate(report, saa_metrics={"cagr": 0.05, "max_drawdown": -0.20, "calmar": 0.25, "sortino": 0.5, "sharpe": 0.35})
        assert all(g.status.value != "fail" for g in results)

    def test_failing_return_gate(self) -> None:
        report = self._make_report()
        engine = GateEngine()
        results = engine.evaluate(report, saa_metrics={"cagr": 0.10, "max_drawdown": -0.20, "calmar": 0.5, "sortino": 0.8})
        return_gate = [g for g in results if g.gate_name == "G2 Return"][0]
        assert return_gate.status.value == "fail"

    def test_overfitting_fails_hard(self) -> None:
        report = self._make_report()
        report.overfitting = OverfittingMetrics(pbo=0.30, deflated_sharpe=0.1, complexity_score=3.0)
        engine = GateEngine()
        results = engine.evaluate(report, saa_metrics={"cagr": 0.05, "max_drawdown": -0.20, "calmar": 0.25})
        overfit_gate = [g for g in results if g.gate_name == "G10 Overfitting"][0]
        assert overfit_gate.status.value == "fail"


class TestCandidateStrategies:
    def test_saa_weights(self) -> None:
        w = static_saa_weights(["A", "B", "C"], {"A": 0.4, "B": 0.35, "C": 0.25})
        assert abs(w.sum() - 1.0) < 1e-6

    def test_risk_managed_reduces_exposure(self) -> None:
        base = pd.Series({"A": 0.5, "B": 0.3, "CASH_CNY": 0.2})
        result = risk_managed_core_weights(base, volatility=0.20, target_vol=0.10)
        assert result["CASH_CNY"] > 0.2

    def test_adaptive_tilt_constrained(self) -> None:
        base = pd.Series({"A": 0.25, "CASH_CNY": 0.75})
        scores = pd.Series({"A": 2.0, "CASH_CNY": 0}, dtype=float)
        tilted = adaptive_core_tilt(base, scores, alpha_v=0.15)
        assert tilted["A"] <= 0.25 * (1 + 0.15)
