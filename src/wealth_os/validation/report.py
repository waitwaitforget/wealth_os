from __future__ import annotations

from dataclasses import dataclass

from .checks import ValidationIssue


@dataclass
class ValidationReport:
    issues: list[ValidationIssue]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def summary(self) -> str:
        if not self.issues:
            return "PASS: no validation issues"
        prefix = "PASS_WITH_WARNINGS" if self.passed else "FAIL"
        return (
            prefix + "\n" + "\n".join(f"[{i.severity}] {i.code}: {i.message}" for i in self.issues)
        )
