"""P5 Backtest & Benchmark tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wealth_os.analytics.attribution import (
    attribute_signals,
)
from wealth_os.analytics.benchmarks import (
    compare_to_benchmarks,
    compute_market_benchmark_nav,
)
from wealth_os.analytics.extended_metrics import (
    cash_contribution,
    conditional_drawdown_at_risk,
    max_drawdown_duration,
    pre_cost_metrics,
    recovery_time,
)
from wealth_os.domain.models import BacktestResult


def _make_result(
    nav_vals: list[float],
    costs: list[float] | None = None,
    cash_vals: list[float] | None = None,
    orders: pd.DataFrame | None = None,
) -> BacktestResult:
    n = len(nav_vals)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    nav = pd.Series(nav_vals, index=idx)
    unit_nav = nav / nav.iloc[0]
    return BacktestResult(
        nav=nav,
        unit_nav=unit_nav,
        units=pd.Series(1000.0, index=idx),
        cash=pd.Series(cash_vals or [100.0] * n, index=idx),
        positions_value=pd.DataFrame({"A": nav - (cash_vals or [100.0] * n)}, index=idx),
        actual_weights=pd.DataFrame({"A": [0.9] * n, "CASH": [0.1] * n}, index=idx),
        target_weights=pd.DataFrame({"A": [0.9] * n, "CASH": [0.1] * n}, index=idx),
        external_cash_flows=pd.Series(0.0, index=idx),
        transaction_costs=pd.Series(costs or [0.0] * n, index=idx),
        turnover=pd.Series([0.0] * n, index=idx),
        orders=orders or pd.DataFrame(),
    )


class TestExtendedMetrics:
    def test_cdar(self) -> None:
        dd_series = pd.Series([0.0, -0.01, -0.02, -0.05, -0.10, -0.03, 0.0])
        cdar = conditional_drawdown_at_risk(dd_series, confidence=0.80)
        assert cdar < 0

    def test_max_dd_duration(self) -> None:
        nav = pd.Series(
            [100, 98, 95, 97, 96, 99, 101],
            index=pd.date_range("2020-01-01", periods=7, freq="B"),
        )
        duration = max_drawdown_duration(nav)
        assert duration > 0

    def test_recovery_time(self) -> None:
        nav = pd.Series(
            [100, 90, 85, 88, 92, 95, 100, 102],
            index=pd.date_range("2020-01-01", periods=8, freq="B"),
        )
        rt = recovery_time(nav)
        assert rt > 0

    def test_pre_cost_metrics(self) -> None:
        result = _make_result(
            nav_vals=list(range(1000, 1100, 10)),
            costs=[1.0] * 10,
        )
        m = pre_cost_metrics(result)
        assert m["twr_post_cost"] < m["twr_pre_cost"]
        assert m["cost_impact_on_twr"] > 0

    def test_cash_contribution(self) -> None:
        nav = pd.Series([1000, 1010, 1020], index=pd.date_range("2020-01-01", periods=3, freq="B"))
        cash = pd.Series([200, 200, 200], index=nav.index)
        result = cash_contribution(nav, cash, cash_yield_annual=0.02)
        assert "cash_contribution_to_twr" in result


class TestBenchmarks:
    def test_market_benchmark_nav(self) -> None:
        idx = pd.date_range("2020-01-01", periods=100, freq="B")
        prices = pd.DataFrame(
            {"A": 100 + np.linspace(0, 20, 100), "B": 50 + np.linspace(0, 10, 100)},
            index=idx,
        )
        nav = compute_market_benchmark_nav(prices, weights={"A": 0.6, "B": 0.4})
        assert len(nav) > 0
        assert nav.iloc[-1] > nav.iloc[0]

    def test_compare_to_benchmarks(self) -> None:
        idx = pd.date_range("2020-01-01", periods=200, freq="B")
        prices = pd.DataFrame(
            {"A": 100 + np.linspace(0, 40, 200), "B": 50 + np.linspace(0, 30, 200)},
            index=idx,
        )
        nav = pd.Series(1000 + np.linspace(0, 200, 200), index=idx)
        result = BacktestResult(
            nav=nav,
            unit_nav=nav / nav.iloc[0],
            units=pd.Series(1000.0, index=idx),
            cash=pd.Series(100.0, index=idx),
            positions_value=pd.DataFrame({"A": nav - 100}, index=idx),
            actual_weights=pd.DataFrame({"A": [0.9] * 200, "CASH": [0.1] * 200}, index=idx),
            target_weights=pd.DataFrame({"A": [0.9] * 200, "CASH": [0.1] * 200}, index=idx),
            external_cash_flows=pd.Series(0.0, index=idx),
            transaction_costs=pd.Series(0.0, index=idx),
            turnover=pd.Series(0.0, index=idx),
            orders=pd.DataFrame(),
        )
        comp = compare_to_benchmarks(result, prices, "Test")
        assert len(comp.results) >= 1


class TestAttribution:
    def test_basic_attribution(self) -> None:
        base = _make_result(list(range(1000, 1100, 10)))
        full = _make_result(list(range(1000, 1120, 12)))

        attr = attribute_signals(
            base_result=base,
            full_result=full,
        )
        assert attr.twr > 0
        assert isinstance(attr.summary(), str)
