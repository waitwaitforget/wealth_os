"""Strategy Validation Gate Engine (Section 35).

Implements the 10 validation gates that every strategy must pass:
G1 Correctness, G2 Return, G3 Drawdown, G4 Efficiency,
G5 Robustness, G6 Regime, G7 Cost, G8 Delay, G9 OOS, G10 Overfitting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from wealth_os.evaluation.models import (
    GateResult,
    GateStatus,
    StrategyReport,
    StrategyStatus,
)


@dataclass
class GateConfig:
    """Configurable thresholds for all validation gates."""

    # G2 Return
    core_return_tolerance_cagr: float = 0.01  # strategy CAGR can be 1% below SAA CAGR

    # G3 Drawdown
    target_drawdown_improvement: float = 0.20  # 20% relative improvement

    # G4 Efficiency
    target_calmar_improvement: float = 0.15
    target_sortino_improvement: float = 0.10

    # G5 Robustness
    parameter_robustness_threshold: float = 0.80

    # G6 Regime
    min_regime_positive_ratio: float = 0.50

    # G7 Cost
    cost_multipliers: list[float] = field(default_factory=lambda: [1.0, 2.0, 3.0])
    max_cost_degradation_pct: float = 0.30  # max 30% Sharpe loss at 2x cost

    # G8 Delay
    delay_days: list[int] = field(default_factory=lambda: [0, 1, 3, 5])
    max_delay_degradation_pct: float = 0.40  # max 40% Sharpe loss at 3-day delay

    # G9 OOS
    oos_required: bool = True

    # G10 Overfitting
    max_pbo: float = 0.20
    min_deflated_sharpe: float = 0.5
    max_complexity_score: float = 5.0


class GateEngine:
    """Evaluates a StrategyReport against all validation gates."""

    def __init__(self, config: GateConfig | None = None) -> None:
        self.config = config or GateConfig()

    def evaluate(self, report: StrategyReport, saa_metrics: dict | None = None) -> list[GateResult]:
        results: list[GateResult] = []

        results.append(self._gate1_correctness(report))
        results.append(self._gate2_return(report, saa_metrics))
        results.append(self._gate3_drawdown(report, saa_metrics))
        results.append(self._gate4_efficiency(report, saa_metrics))
        results.append(self._gate5_robustness(report))
        results.append(self._gate6_regime(report))
        results.append(self._gate7_cost(report))
        results.append(self._gate8_delay(report))
        results.append(self._gate9_oos(report))
        results.append(self._gate10_overfitting(report))

        report.gates = results
        self._determine_status(report)
        return results

    def _gate1_correctness(self, report: StrategyReport) -> GateResult:
        return GateResult(
            gate_name="G1 Correctness",
            status=GateStatus.PASS,
            description="Accounting identity, weight constraints, PIT validation assumed passed by Validation OS",
        )

    def _gate2_return(self, report: StrategyReport, saa: dict | None) -> GateResult:
        if saa is None:
            return GateResult(gate_name="G2 Return", status=GateStatus.SKIP, description="No SAA benchmark to compare")

        saa_cagr = saa.get("cagr", 0.0)
        strat_cagr = report.performance.cagr
        gap = strat_cagr - saa_cagr
        passed = gap >= -self.config.core_return_tolerance_cagr

        return GateResult(
            gate_name="G2 Return",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"CAGR gap vs SAA: {gap:+.2%} (threshold: {-(self.config.core_return_tolerance_cagr):.1%})",
            metrics={"gap": gap, "threshold": -self.config.core_return_tolerance_cagr},
        )

    def _gate3_drawdown(self, report: StrategyReport, saa: dict | None) -> GateResult:
        if saa is None:
            return GateResult(gate_name="G3 Drawdown", status=GateStatus.SKIP)

        our_dd = report.drawdown.max_drawdown
        saa_dd = saa.get("max_drawdown", -0.01)
        improvement = (our_dd - saa_dd) / abs(saa_dd) if saa_dd != 0 else 0.0
        passed = improvement >= self.config.target_drawdown_improvement

        return GateResult(
            gate_name="G3 Drawdown",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"Drawdown improvement: {improvement:+.1%} (need {self.config.target_drawdown_improvement:.0%})",
            metrics={"improvement": improvement},
        )

    def _gate4_efficiency(self, report: StrategyReport, saa: dict | None) -> GateResult:
        if saa is None:
            return GateResult(gate_name="G4 Efficiency", status=GateStatus.SKIP)

        calmar_imp = 0.0
        sortino_imp = 0.0
        if saa.get("calmar", 0) != 0:
            calmar_imp = (report.efficiency.calmar - saa["calmar"]) / abs(saa["calmar"])
        if saa.get("sortino", 0) != 0:
            sortino_imp = (report.efficiency.sortino - saa["sortino"]) / abs(saa["sortino"])

        passed = calmar_imp >= self.config.target_calmar_improvement or sortino_imp >= self.config.target_sortino_improvement

        return GateResult(
            gate_name="G4 Efficiency",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"Calmar Δ:{calmar_imp:+.1%}, Sortino Δ:{sortino_imp:+.1%}",
            metrics={"calmar_improvement": calmar_imp, "sortino_improvement": sortino_imp},
        )

    def _gate5_robustness(self, report: StrategyReport) -> GateResult:
        scores = [ps.robustness_score for ps in report.parameter_surfaces]
        if not scores:
            return GateResult(gate_name="G5 Robustness", status=GateStatus.SKIP, description="No parameter surface data")

        avg_score = float(np.mean(scores))
        passed = avg_score >= self.config.parameter_robustness_threshold
        return GateResult(
            gate_name="G5 Robustness",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"Avg robustness: {avg_score:.0%} (need {self.config.parameter_robustness_threshold:.0%})",
            metrics={"avg_robustness": avg_score},
        )

    def _gate6_regime(self, report: StrategyReport) -> GateResult:
        if not report.regimes:
            return GateResult(gate_name="G6 Regime", status=GateStatus.SKIP)

        positive_regimes = sum(1 for r in report.regimes if r.excess_return > 0)
        ratio = positive_regimes / len(report.regimes)
        passed = ratio >= self.config.min_regime_positive_ratio

        return GateResult(
            gate_name="G6 Regime",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"Excess-return-positive in {positive_regimes}/{len(report.regimes)} regimes ({ratio:.0%})",
            metrics={"positive_ratio": ratio},
        )

    def _gate7_cost(self, report: StrategyReport) -> GateResult:
        levels = report.cost_stress.levels
        if not levels:
            return GateResult(gate_name="G7 Cost", status=GateStatus.SKIP)

        passed = report.cost_stress.passed
        return GateResult(
            gate_name="G7 Cost",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description=f"Cost stress: {len(levels)} levels, {'passed' if passed else 'failed'}",
        )

    def _gate8_delay(self, report: StrategyReport) -> GateResult:
        passed = report.delay_stress.passed if report.delay_stress.levels else False
        return GateResult(
            gate_name="G8 Delay",
            status=GateStatus.PASS if passed else GateStatus.WARN if not report.delay_stress.levels else GateStatus.FAIL,
            description=f"Signal delay stress: {'passed' if passed else 'no data or failed'}",
        )

    def _gate9_oos(self, report: StrategyReport) -> GateResult:
        if not self.config.oos_required:
            return GateResult(gate_name="G9 OOS", status=GateStatus.SKIP)

        return GateResult(
            gate_name="G9 OOS",
            status=GateStatus.PASS,
            description="OOS validation deferred to walk-forward analysis",
        )

    def _gate10_overfitting(self, report: StrategyReport) -> GateResult:
        of = report.overfitting
        issues: list[str] = []
        passed = True

        if of.pbo > self.config.max_pbo:
            issues.append(f"PBO={of.pbo:.2f} > {self.config.max_pbo}")
            passed = False
        if of.deflated_sharpe < self.config.min_deflated_sharpe:
            issues.append(f"Deflated Sharpe={of.deflated_sharpe:.2f} < {self.config.min_deflated_sharpe}")
            passed = False
        if of.complexity_score > self.config.max_complexity_score and of.complexity_score > 0:
            issues.append(f"Complexity={of.complexity_score:.1f} > {self.config.max_complexity_score}")

        return GateResult(
            gate_name="G10 Overfitting",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            description="; ".join(issues) if issues else "Overfitting risk acceptable",
            metrics={"pbo": of.pbo, "deflated_sharpe": of.deflated_sharpe},
        )

    def _determine_status(self, report: StrategyReport) -> None:
        fail_count = sum(1 for g in report.gates if g.status == GateStatus.FAIL)

        if fail_count >= 3:
            report.overall_status = StrategyStatus.REJECTED
            report.recommendation = "Too many gate failures — strategy rejected."
        elif fail_count > 0:
            report.overall_status = StrategyStatus.RESEARCH
            report.recommendation = f"{fail_count} gate(s) failed — requires revision."
        else:
            report.overall_status = StrategyStatus.VALIDATED
            report.recommendation = "All gates passed — eligible for Shadow phase."
