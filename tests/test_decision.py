"""P6 Decision Engine tests."""

from __future__ import annotations

import pandas as pd
import pytest

from wealth_os.decision.engine import (
    Priority,
    generate_decision,
)
from wealth_os.decision.logger import (
    DecisionLogger,
    compute_execution_deviation,
)


class TestDecisionEngine:
    def test_generate_decision_report(self) -> None:
        cur = pd.Series({"A": 0.30, "B": 0.40, "CASH": 0.30})
        tgt = pd.Series({"A": 0.35, "B": 0.35, "CASH": 0.30})
        base = pd.Series({"A": 0.30, "B": 0.40, "CASH": 0.30})
        val = pd.Series({"A": 1.0, "B": -1.0})
        trnd = pd.Series({"A": 0.5, "B": 0.5})

        report = generate_decision(
            date=pd.Timestamp("2024-01-15"),
            current_weights=cur,
            target_weights=tgt,
            value_scores=val,
            trend_scores=trnd,
            base_weights=base,
            trigger_reasons=["weight drift"],
            portfolio_vol=0.12,
            drawdown=-0.03,
            min_trade_fraction=0.001,
        )

        assert len(report.decisions) == 3
        assert len(report.active_decisions) == 2
        deltas = sorted([d.delta for d in report.active_decisions])
        assert deltas[0] == pytest.approx(-0.05)
        assert deltas[1] == pytest.approx(0.05)
        assert not report.is_no_action

    def test_no_action_decision(self) -> None:
        cur = pd.Series({"A": 0.50, "CASH": 0.50})
        tgt = pd.Series({"A": 0.50, "CASH": 0.50})

        report = generate_decision(
            date=pd.Timestamp("2024-01-15"),
            current_weights=cur,
            target_weights=tgt,
            min_trade_fraction=0.01,
        )
        assert report.is_no_action

    def test_confidence_scoring(self) -> None:
        cur = pd.Series({"A": 0.30, "CASH": 0.70})
        tgt = pd.Series({"A": 0.50, "CASH": 0.50})
        base = pd.Series({"A": 0.30, "CASH": 0.70})
        val = pd.Series({"A": 2.0})
        trnd = pd.Series({"A": 2.0})

        report = generate_decision(
            date=pd.Timestamp("2024-01-15"),
            current_weights=cur,
            target_weights=tgt,
            value_scores=val,
            trend_scores=trnd,
            base_weights=base,
            min_trade_fraction=0.001,
        )

        assert report.overall_confidence > 0.7

    def test_priority_assignment(self) -> None:
        cur = pd.Series({"A": 0.10, "B": 0.20, "C": 0.10, "CASH": 0.60})
        tgt = pd.Series({"A": 0.30, "B": 0.10, "C": 0.25, "CASH": 0.35})

        report = generate_decision(
            date=pd.Timestamp("2024-01-15"),
            current_weights=cur,
            target_weights=tgt,
            min_trade_fraction=0.001,
        )
        priorities = {d.asset: d.priority for d in report.decisions}
        assert priorities.get("A") == Priority.HIGH
        assert priorities.get("C") == Priority.HIGH

    def test_summary_output(self) -> None:
        cur = pd.Series({"A": 0.30, "CASH": 0.70})
        tgt = pd.Series({"A": 0.50, "CASH": 0.50})

        report = generate_decision(
            date=pd.Timestamp("2024-01-15"),
            current_weights=cur,
            target_weights=tgt,
            trigger_reasons=["weight drift 20%"],
        )
        summary = report.summary()
        assert "REBALANCE" in summary
        assert "A" in summary


class TestDecisionLogger:
    def test_record_and_review(self) -> None:
        logger = DecisionLogger(strategy_id="test")
        cur = pd.Series({"A": 0.30, "CASH": 0.70})
        tgt = pd.Series({"A": 0.50, "CASH": 0.50})

        for i in range(10):
            report = generate_decision(
                date=pd.Timestamp(f"2024-01-{i + 1:02d}"),
                current_weights=cur,
                target_weights=tgt,
                min_trade_fraction=0.001,
            )
            logger.record(report)

        stats = logger.review()
        assert stats["total_decisions"] == 10
        assert stats["total_trades"] == 20

    def test_dataframe_export(self) -> None:
        logger = DecisionLogger()
        cur = pd.Series({"A": 0.30, "CASH": 0.70})
        tgt = pd.Series({"A": 0.50, "CASH": 0.50})

        for i in range(3):
            report = generate_decision(
                date=pd.Timestamp(f"2024-01-{i + 1:02d}"),
                current_weights=cur,
                target_weights=tgt,
                min_trade_fraction=0.001,
            )
            logger.record(report)

        df = logger.to_dataframe()
        assert len(df) == 3
        assert "n_trades" in df.columns

    def test_execution_deviation(self) -> None:
        idx = pd.date_range("2024-01-01", periods=5, freq="B")
        suggested = pd.DataFrame(
            {"A": [0.3, 0.3, 0.5, 0.5, 0.5], "CASH": [0.7, 0.7, 0.5, 0.5, 0.5]},
            index=idx,
        )
        actual = pd.DataFrame(
            {"A": [0.3, 0.32, 0.48, 0.5, 0.51], "CASH": [0.7, 0.68, 0.52, 0.5, 0.49]},
            index=idx,
        )
        dev = compute_execution_deviation(suggested, actual)
        assert len(dev) == 5
        assert dev["total_abs_deviation"].iloc[-1] < 0.05
