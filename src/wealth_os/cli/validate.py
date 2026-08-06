"""Unified validation report — runs all P4 validation gates.

Usage:
    python -m wealth_os.cli.validate --type data --data-dir data
    python -m wealth_os.cli.validate --type strategy --strategy-id vtr_v1
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime

from wealth_os.validation.governance import StrategyLifecycle, StrategyState


@dataclass
class ValidationGate:
    name: str
    passed: bool
    details: str = ""
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass
class UnifiedValidationReport:
    report_id: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    gates: list[ValidationGate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates) and len(self.errors) == 0

    def add_gate(self, gate: ValidationGate) -> None:
        self.gates.append(gate)
        if not gate.passed:
            self.errors.append(f"[{gate.name}] {gate.details}")

    def summary(self) -> str:
        lines = ["=" * 60, "  VALIDATION REPORT", "=" * 60]
        for g in self.gates:
            status = "PASS" if g.passed else "FAIL"
            lines.append(f"  [{status}] {g.name}")
            if g.details:
                lines.append(f"         {g.details}")
        lines.append("=" * 60)
        overall = "ALL GATES PASSED" if self.all_passed else "SOME GATES FAILED"
        lines.append(f"  {overall}")
        return "\n".join(lines)


def run_data_validation(data_dir: str) -> list[ValidationGate]:
    gates: list[ValidationGate] = []

    try:
        from wealth_os.infrastructure.data.repository import ParquetRepository
        from wealth_os.validation.data_checks import DataBundleValidator

        repo = ParquetRepository(root_dir=data_dir)
        version = repo.get_latest_version()

        if version is None:
            gates.append(ValidationGate("data_version", False, "No data version found"))
            return gates

        instruments = repo.load_instruments()
        if not instruments:
            gates.append(ValidationGate("instruments", False, "No instruments loaded"))
            return gates

        ids = [i.instrument_id for i in instruments]
        bundle = repo.load_bundle(
            ids, start=date(2000, 1, 1), end=date(2099, 12, 31), version=version
        )
        health = DataBundleValidator().validate(bundle)

        gates.append(
            ValidationGate(
                name="data_quality",
                passed=health.passed,
                details=f"{health.error_count} errors, {health.warning_count} warnings",
                metrics={
                    "errors": health.error_count,
                    "warnings": health.warning_count,
                    "instruments": len(instruments),
                },
            )
        )

        gates.append(
            ValidationGate(
                name="data_version",
                passed=True,
                details=f"Version: {version.version_id}",
                metrics={"version": version.version_id},
            )
        )

    except Exception as e:
        gates.append(ValidationGate("data_validation", False, f"Error: {e}"))

    return gates


def run_strategy_validation(strategy_id: str) -> list[ValidationGate]:
    gates: list[ValidationGate] = []

    lifecycle = StrategyLifecycle(strategy_id=strategy_id)
    gates.append(
        ValidationGate(
            name="strategy_state",
            passed=lifecycle.current_state != StrategyState.SUSPENDED,
            details=f"State: {lifecycle.current_state}",
            metrics={"transitions": len(lifecycle.history)},
        )
    )

    return gates


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Validation Report")
    parser.add_argument("--type", type=str, default="data", choices=["data", "strategy", "all"])
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--strategy-id", type=str, default="vtr_v1")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    report = UnifiedValidationReport(report_id=datetime.now().strftime("%Y%m%d_%H%M%S"))

    if args.type in ("data", "all"):
        for g in run_data_validation(args.data_dir):
            report.add_gate(g)

    if args.type in ("strategy", "all"):
        for g in run_strategy_validation(args.strategy_id):
            report.add_gate(g)

    if report.gates:
        report.report_id = f"validate_{report.gates[0].name}_{report.report_id}"

    if args.json:
        output = {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "all_passed": report.all_passed,
            "gates": [
                {
                    "name": g.name,
                    "passed": g.passed,
                    "details": g.details,
                    "metrics": g.metrics,
                }
                for g in report.gates
            ],
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(report.summary())

    sys.exit(0 if report.all_passed else 1)


if __name__ == "__main__":
    main()
