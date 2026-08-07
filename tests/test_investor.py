"""Investor Simulation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wealth_os.backtest.investor import (
    compute_probabilities,
    compute_starting_points,
    compute_underwater_metrics,
    simulate_investor,
)


class TestInvestorSimulation:
    def test_basic_contribution(self) -> None:
        idx = pd.date_range("2020-01-01", periods=500, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.3, 500), index=idx)
        result = simulate_investor(nav, initial_capital=1_000_000, monthly_contribution=50_000)
        assert result.final_wealth > result.total_contributed
        assert result.investment_profit > 0

    def test_twr_unchanged_by_contributions(self) -> None:
        """TWR should be the same regardless of contributions (unit NAV invariant)."""
        idx = pd.date_range("2020-01-01", periods=252, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.15, 252), index=idx)
        r1 = simulate_investor(nav, initial_capital=100_000, monthly_contribution=0)
        r2 = simulate_investor(nav, initial_capital=100_000, monthly_contribution=50_000)
        assert abs(r1.twr - r2.twr) < 0.01

    def test_xirr_with_contributions(self) -> None:
        idx = pd.date_range("2020-01-01", periods=252, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.20, 252), index=idx)
        result = simulate_investor(nav, initial_capital=500_000, monthly_contribution=30_000)
        assert not np.isnan(result.xirr_value)


class TestUnderwater:
    def test_underwater_ratio(self) -> None:
        idx = pd.date_range("2020-01-01", periods=300, freq="B")
        rng = np.random.RandomState(42)
        nav = pd.Series(1.0 + np.exp(rng.standard_normal(300).cumsum() * 0.01), index=idx)
        report = compute_underwater_metrics(nav)
        assert 0 <= report.underwater_ratio <= 1

    def test_recovery_computed(self) -> None:
        idx = pd.date_range("2020-01-01", periods=500, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.15, 500), index=idx)
        report = compute_underwater_metrics(nav)
        assert report.longest_underwater_days >= 0


class TestStartingPoints:
    def test_multi_start(self) -> None:
        idx = pd.date_range("2015-01-01", periods=1500, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.8, 1500), index=idx)
        result = compute_starting_points(nav, holding_years=3, step_months=6)
        assert result.n_start_points > 0
        assert result.positive_ratio > 0.5

    def test_distribution_output(self) -> None:
        idx = pd.date_range("2015-01-01", periods=1200, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.5, 1200), index=idx)
        result = compute_starting_points(nav, holding_years=3)
        assert result.median_cagr <= result.p90_cagr
        assert result.worst_cagr <= result.median_cagr


class TestProbability:
    def test_no_crash_scenario(self) -> None:
        idx = pd.date_range("2015-01-01", periods=1500, freq="B")
        nav = pd.Series(1.0 + np.linspace(0, 0.6, 1500), index=idx)
        probs = compute_probabilities(nav)
        assert probs.p_5y_negative == 0.0
