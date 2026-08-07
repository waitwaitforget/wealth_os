"""P9 Paper Trading tests."""

from __future__ import annotations

import pandas as pd
import pytest

from wealth_os.execution.adapter import DummyBrokerAdapter
from wealth_os.execution.broker import (
    Order,
    OrderSide,
    OrderStatus,
    PaperBroker,
)
from wealth_os.execution.reconciliation import (
    ExecutionMonitor,
    SlippageReport,
    reconcile_model_vs_actual,
)


class TestPaperBroker:
    def test_plan_orders(self) -> None:
        broker = PaperBroker(cash=100_000)
        target = pd.Series({"A": 0.60, "CASH": 0.40})
        positions = {"A": 30}
        prices = pd.Series({"A": 100.0})
        nav = 100_000.0

        orders = broker.plan_orders(target, positions, prices, nav)
        assert len(orders) > 0

    def test_execute_market_buy(self) -> None:
        broker = PaperBroker(cash=100_000, commission_bps=1.0, slippage_bps=2.0)
        order = Order(
            order_id="T1",
            symbol="A",
            side=OrderSide.BUY,
            quantity=100,
            notional=10_000,
            status=OrderStatus.APPROVED,
        )

        filled = broker.execute_market(order, reference_price=100)
        assert filled.status == OrderStatus.FILLED
        assert filled.fill_price > 100  # buy slippage
        assert broker.positions["A"] == 100
        assert broker.cash < 100_000

    def test_execute_market_sell(self) -> None:
        broker = PaperBroker(cash=100_000)
        broker.positions["A"] = 200
        order = Order(
            order_id="T2",
            symbol="A",
            side=OrderSide.SELL,
            quantity=100,
            notional=10_000,
            status=OrderStatus.APPROVED,
        )

        filled = broker.execute_market(order, reference_price=100)
        assert filled.status == OrderStatus.FILLED
        assert filled.fill_price < 100  # sell slippage
        assert broker.positions["A"] == 100

    def test_lot_rounding(self) -> None:
        broker = PaperBroker(cash=100_000, lot_sizes={"A": 100})
        assert broker._round_to_lot(245, "A") == 200
        assert broker._round_to_lot(50, "A") == 0


class TestReconciliation:
    def test_reconcile_weights(self) -> None:
        model = pd.Series({"A": 0.50, "B": 0.30, "CASH": 0.20})
        positions = {"A": 40, "B": 25}
        prices = pd.Series({"A": 100, "B": 100})
        nav = 8000.0

        result = reconcile_model_vs_actual(model, positions, prices, nav)
        assert result["A"]["actual_weight"] == pytest.approx(0.50)
        assert result["B"]["actual_weight"] == pytest.approx(0.3125)


class TestSlippageReport:
    def test_empty_report(self) -> None:
        report = SlippageReport()
        assert report.avg_slippage_bps == 0.0

    def test_with_orders(self) -> None:
        o1 = Order(
            order_id="O1",
            symbol="A",
            side=OrderSide.BUY,
            quantity=100,
            notional=10000,
            status=OrderStatus.FILLED,
            slippage_bps=5.0,
            commission=3.0,
        )
        o2 = Order(
            order_id="O2",
            symbol="A",
            side=OrderSide.SELL,
            quantity=50,
            notional=5000,
            status=OrderStatus.FILLED,
            slippage_bps=10.0,
            commission=1.5,
        )
        report = SlippageReport(orders=[o1, o2])
        assert report.avg_slippage_bps == 7.5
        assert report.total_commission == 4.5


class TestExecutionMonitor:
    def test_high_slippage_alert(self) -> None:
        monitor = ExecutionMonitor(max_slippage_warn_bps=20, max_slippage_crit_bps=50)
        order = Order(
            order_id="O1",
            symbol="A",
            side=OrderSide.BUY,
            quantity=100,
            notional=10000,
            status=OrderStatus.FILLED,
            slippage_bps=30.0,
            filled_quantity=100,
        )
        alerts = monitor.check_order(order, 100)
        assert len(alerts) == 1
        assert alerts[0].level.value == "warning"

    def test_critical_slippage(self) -> None:
        monitor = ExecutionMonitor(max_slippage_crit_bps=50)
        order = Order(
            order_id="O1",
            symbol="A",
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.FILLED,
            slippage_bps=60.0,
            filled_quantity=100,
        )
        alerts = monitor.check_order(order, 100)
        assert alerts[0].level.value == "critical"


class TestBrokerAdapter:
    def test_dummy_adapter(self) -> None:
        broker = PaperBroker(cash=100_000)
        adapter = DummyBrokerAdapter(broker)
        assert adapter.name == "dummy"
        assert not adapter.is_live
        assert adapter.check_connection()
        assert adapter.get_cash_balance() == 100_000
