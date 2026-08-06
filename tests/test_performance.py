import pandas as pd

from wealth_os.analytics.performance import performance_summary, time_weighted_return, wealth_summary


def test_wealth_summary_separates_contributions_from_profit() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-02-01"])
    nav = pd.Series([1_000.0, 1_250.0], index=dates)
    flows = pd.Series([0.0, 100.0], index=dates)
    summary = wealth_summary(nav, flows, initial_capital=1_000.0)

    assert summary["net_invested_capital"] == 1_100.0
    assert summary["investment_profit"] == 150.0


def test_twr_includes_first_day_cost_against_opening_nav() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    unit_nav = pd.Series([0.99, 1.00], index=dates)

    assert time_weighted_return(unit_nav, initial_unit_nav=1.0) == 0.0


def test_performance_summary_reports_calendar_interval_and_annualized_return() -> None:
    dates = pd.to_datetime(["2020-01-01", "2021-01-01"])
    unit_nav = pd.Series([1.0, 1.10], index=dates)
    summary = performance_summary(unit_nav, initial_unit_nav=None)

    assert summary["start_date"] == dates[0]
    assert summary["end_date"] == dates[1]
    assert summary["calendar_days"] == 366.0
    assert 0.99 < summary["years"] < 1.01
    assert summary["annualized_return"] == summary["cagr"]
    assert 0.099 < summary["annualized_return"] < 0.101
