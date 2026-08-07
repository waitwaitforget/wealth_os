"""Strategy Evaluation Domain Models — DTOs for the validation framework.

Defines: StrategyReport, Gate, GateResult, ExperimentRegistry,
StrategyStatus, and all metrics types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StrategyStatus(StrEnum):
    REJECTED = "rejected"
    RESEARCH = "research"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class GateResult:
    gate_name: str
    status: GateStatus
    description: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    twr: float = 0.0
    cagr: float = 0.0
    annualized_return: float = 0.0
    xirr: float | None = None
    excess_return: float = 0.0


@dataclass
class RiskMetricsDTO:
    annualized_volatility: float = 0.0
    downside_volatility: float = 0.0
    var_95: float = 0.0
    expected_shortfall_95: float = 0.0
    beta: float = 1.0


@dataclass
class DrawdownMetrics:
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_dd_duration_days: float = 0.0
    recovery_time_days: float = 0.0
    ulcer_index: float = 0.0


@dataclass
class EfficiencyMetrics:
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    information_ratio: float = 0.0


@dataclass
class RollingMetrics:
    window_days: int = 0
    median: float = 0.0
    p10: float = 0.0
    worst: float = 0.0
    positive_ratio: float = 0.0
    benchmark_win_rate: float = 0.0


@dataclass
class RegimeResult:
    regime_name: str = ""
    strategy_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    expected_shortfall: float = 0.0
    avg_cash: float = 0.0
    turnover: float = 0.0


@dataclass
class AblationResult:
    component: str = ""
    delta_cagr: float = 0.0
    delta_max_dd: float = 0.0
    delta_calmar: float = 0.0
    delta_turnover: float = 0.0
    delta_cost: float = 0.0


@dataclass
class ParameterSurfaceResult:
    param_name: str = ""
    values: list[dict[str, float]] = field(default_factory=list)
    robustness_score: float = 0.0


@dataclass
class StressTestResult:
    stress_type: str = ""
    levels: list[dict[str, float]] = field(default_factory=list)
    passed: bool = False


@dataclass
class OverfittingMetrics:
    pbo: float = 0.0  # Probability of Backtest Overfitting
    deflated_sharpe: float = 0.0
    experiment_count: int = 0
    parameter_count: int = 0
    complexity_score: float = 0.0


@dataclass
class ExperimentRecord:
    experiment_id: str = ""
    strategy_id: str = ""
    strategy_version: str = "0.1.0"
    code_version: str = "0.1.0"
    data_version: str = ""
    benchmark_id: str = ""
    parameter_space: dict[str, Any] = field(default_factory=dict)
    research_period: str = ""
    validation_period: str = ""
    oos_period: str = ""
    created_at: str = ""
    hypothesis: str = ""
    result_summary: str = ""
    gate_status: str = ""
    notes: str = ""


@dataclass
class StrategyReport:
    """Comprehensive strategy evaluation report (Section 11)."""

    strategy_id: str = ""
    strategy_version: str = "0.1.0"
    generated_at: str = ""

    # Core metrics
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    risk: RiskMetricsDTO = field(default_factory=RiskMetricsDTO)
    drawdown: DrawdownMetrics = field(default_factory=DrawdownMetrics)
    efficiency: EfficiencyMetrics = field(default_factory=EfficiencyMetrics)

    # Analysis
    rolling_1y: RollingMetrics = field(default_factory=RollingMetrics)
    rolling_3y: RollingMetrics = field(default_factory=RollingMetrics)
    rolling_5y: RollingMetrics = field(default_factory=RollingMetrics)
    regimes: list[RegimeResult] = field(default_factory=list)
    ablation: list[AblationResult] = field(default_factory=list)
    parameter_surfaces: list[ParameterSurfaceResult] = field(default_factory=list)
    cost_stress: StressTestResult = field(default_factory=StressTestResult)
    delay_stress: StressTestResult = field(default_factory=StressTestResult)
    data_stress: StressTestResult = field(default_factory=StressTestResult)

    # Statistical
    relative_nav_beta: float = 1.0
    overfitting: OverfittingMetrics = field(default_factory=OverfittingMetrics)

    # Governance
    gates: list[GateResult] = field(default_factory=list)
    overall_status: StrategyStatus = StrategyStatus.RESEARCH
    recommendation: str = ""

    @property
    def all_gates_passed(self) -> bool:
        return all(g.status != GateStatus.FAIL for g in self.gates) and len(self.gates) > 0
