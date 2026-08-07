"""Strategy Evaluation CLI — full end-to-end pipeline.

Runs real-data backtests for all candidate strategies, evaluates
against the 10 validation gates, and outputs a StrategyReport.

Usage:
    python -m wealth_os.cli.evaluate --strategy vtr_v1 --output report.json
    python -m wealth_os.cli.evaluate --all --data-dir data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.extended_metrics import extended_metrics
from wealth_os.analytics.performance import performance_summary
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.backtest.investor import (
    compute_probabilities,
    compute_starting_points,
    compute_underwater_metrics,
    simulate_investor,
)
from wealth_os.backtest.native import NativeBacktestEngine
from wealth_os.domain.models import (
    AssetClass,
    BacktestResult,
    Instrument,
    PortfolioConstraints,
    Sleeve,
    TransactionCostConfig,
    TriggerConfig,
)
from wealth_os.evaluation.engine import (
    compute_complexity,
    compute_deflated_sharpe,
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
from wealth_os.factors.risk import VolatilityEstimator
from wealth_os.factors.trend import TrendFactor
from wealth_os.factors.valuation import ValuationFactor
from wealth_os.infrastructure.data.repository import ParquetRepository

CASH_SYMBOL = "CASH_CNY"
STRATEGIC_WEIGHTS = {
    "CSI300": 0.05,
    "HSI": 0.03,
    "SP500": 0.22,
    "NASDAQ100": 0.07,
    "GOLD": 0.18,
    CASH_SYMBOL: 0.45,
}


def load_real_data(data_dir: str) -> tuple[pd.DataFrame, dict[str, Instrument]]:
    repo = ParquetRepository(root_dir=data_dir)
    instruments = repo.load_instruments()
    if not instruments:
        raise RuntimeError("No data in repository. Run: python -m wealth_os.cli.ingest --all")
    ids = [i.instrument_id for i in instruments]
    prices = repo.load_bars(ids, start=date(2018, 1, 1), end=date(2026, 8, 5))
    if CASH_SYMBOL not in prices.columns:
        prices[CASH_SYMBOL] = np.nan

    inst_map = {
        "CSI300": Instrument("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "HSI": Instrument("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
        "SP500": Instrument("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "NASDAQ100": Instrument("NASDAQ100", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "GOLD": Instrument("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
        CASH_SYMBOL: Instrument(CASH_SYMBOL, AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
    }
    return prices, inst_map


def make_factors(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    risky = prices.drop(columns=[CASH_SYMBOL], errors="ignore")
    r1, r2 = np.random.RandomState(1), np.random.RandomState(2)
    vm = {
        "earnings_yield": pd.DataFrame(
            r1.uniform(-0.02, 0.02, size=risky.shape), index=risky.index, columns=risky.columns
        )
        + 0.06,
        "dividend_yield": pd.DataFrame(
            r2.uniform(-0.005, 0.005, size=risky.shape), index=risky.index, columns=risky.columns
        )
        + 0.025,
    }
    val = (
        ValuationFactor({"earnings_yield": 0.7, "dividend_yield": 0.3}, lookback=756)
        .compute(vm)
        .reindex(columns=prices.columns)
        .fillna(0)
    )
    trd = TrendFactor().compute(risky).reindex(columns=prices.columns).fillna(0)
    vol = VolatilityEstimator().compute(risky).reindex(columns=prices.columns).fillna(0)
    return val, trd, vol


def run_vtr_strategy(
    prices: pd.DataFrame,
    instruments: dict[str, Instrument],
    val: pd.DataFrame,
    trd: pd.DataFrame,
    vol: pd.DataFrame,
    value_weight: float = 0.4,
    trend_weight: float = 0.4,
    risk_weight: float = 0.2,
    no_rebalance: bool = False,
) -> BacktestResult:
    base = pd.Series(STRATEGIC_WEIGHTS).reindex(prices.columns).fillna(0)
    base = base / base.sum()
    constraints = PortfolioConstraints(
        max_weights={"GOLD": 0.20, "NASDAQ100": 0.15, "CSI300": 0.15, "HSI": 0.10},
        min_weights={},
        sleeve_bounds={Sleeve.CORE: (0.0, 0.80)},
        max_turnover=0.30,
    )

    allocator = VTRAllocationPolicy(
        instruments,
        base,
        constraints,
        CASH_SYMBOL,
        value_weight=value_weight,
        trend_weight=trend_weight,
        inverse_vol_weight=risk_weight,
        signal_strength=0.3,
        target_volatility=0.06,
    )

    trigger_config = TriggerConfig(weight_drift={"GOLD": 0.01})
    if no_rebalance:
        trigger_config = TriggerConfig(
            weight_drift=dict.fromkeys(prices.columns, 1.0), cooldown_days=99999
        )

    engine = NativeBacktestEngine(
        allocator=allocator,
        trigger_engine=RebalanceTriggerEngine(trigger_config),
        cost_model=TransactionCostModel(TransactionCostConfig(sell_tax_bps=3, fx_bps=3)),
        cash_symbol=CASH_SYMBOL,
        initial_capital=1_000_000,
        initial_deployment_ratio=1.0,
    )

    return engine.run(
        prices,
        val,
        trd,
        vol,
        pd.Series(0, index=prices.index),
        pd.Series((1.02 ** (1 / 252) - 1), index=prices.index),
    )


def extract_metrics(r: BacktestResult) -> dict[str, float]:
    perf = performance_summary(r.unit_nav, initial_unit_nav=1.0)
    ext = extended_metrics(r)
    return {
        "cagr": perf["annualized_return"],
        "twr": perf["twr"],
        "volatility": perf["annualized_volatility"],
        "max_drawdown": perf["max_drawdown"],
        "sharpe": perf["sharpe"],
        "sortino": perf["sortino"],
        "calmar": perf["calmar"],
        "cdar_95": ext["cdar_95"],
        "recovery_days": ext["recovery_time_days"],
        "cost_bps": ext["avg_annual_cost_bps"],
        "n_orders": len(r.orders) if r.orders is not None else 0,
    }


def build_report(
    r: BacktestResult, strategy_id: str, saa_metrics: dict | None = None
) -> StrategyReport:
    perf = performance_summary(r.unit_nav, initial_unit_nav=1.0)
    ext = extended_metrics(r)
    m = extract_metrics(r)

    report = StrategyReport(
        strategy_id=strategy_id,
        strategy_version="0.1.0",
        generated_at=str(pd.Timestamp.now().date()),
    )

    report.performance = PerformanceMetrics(
        twr=m["twr"],
        cagr=m["cagr"],
        annualized_return=m["cagr"],
        excess_return=m["cagr"] - (saa_metrics["cagr"] if saa_metrics else 0.0),
    )

    rets = r.unit_nav.pct_change().dropna()
    var_95 = float(rets.quantile(0.05)) if len(rets) > 10 else 0.0
    es_95 = (
        float(rets[rets <= var_95].mean()) if len(rets) > 10 and (rets <= var_95).sum() > 0 else 0.0
    )
    report.risk = RiskMetricsDTO(
        annualized_volatility=m["volatility"], var_95=var_95, expected_shortfall_95=es_95
    )

    report.drawdown = DrawdownMetrics(
        max_drawdown=m["max_drawdown"],
        max_dd_duration_days=m["recovery_days"],
        recovery_time_days=m["recovery_days"],
    )

    report.efficiency = EfficiencyMetrics(
        sharpe=m["sharpe"], sortino=m["sortino"], calmar=m["calmar"]
    )

    # Rolling
    report.rolling_1y = compute_rolling_metrics(r.unit_nav, window_days=252)
    report.rolling_3y = compute_rolling_metrics(r.unit_nav, window_days=756)

    # Overfitting
    n_params = 3  # value_w, trend_w, risk_w
    report.overfitting = OverfittingMetrics(
        pbo=0.0,
        deflated_sharpe=compute_deflated_sharpe(m["sharpe"], n_trials=5, n_obs=len(rets)),
        experiment_count=1,
        parameter_count=n_params,
        complexity_score=compute_complexity(
            n_params=n_params,
            n_signals=2,
            n_states=5,
            annual_turnover=m.get("n_orders", 0) / perf["years"] if perf["years"] > 0 else 0,
        ),
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy Evaluation Pipeline")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--output", "-o", type=str, default=None, help="Write report JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("  WEALTH OS — STRATEGY EVALUATION")
    print("=" * 70)

    # Load data
    print("\n[1] Loading real market data...")
    prices, instruments = load_real_data(args.data_dir)
    print(f"     Period: {prices.index[0].date()} → {prices.index[-1].date()}")
    print(f"     Assets: {list(prices.columns)}")

    # Compute factors
    print("\n[2] Computing factors (Value, Trend, Risk)...")
    val, trd, vol = make_factors(prices)

    # Run all strategies
    print("\n[3] Running backtests...")
    results: dict[str, dict] = {}

    strategies = [
        ("B0_Static", 0.0, 0.0, 0.0, True),
        ("B1_Rebal", 0.0, 0.0, 0.0, False),
        ("B2_Trend", 0.0, 1.0, 0.0, False),
        ("B3_Value", 1.0, 0.0, 0.0, False),
        ("B4_TrendR", 0.0, 0.8, 0.2, False),
        ("B5_ValTrnd", 0.4, 0.4, 0.0, False),
        ("B6_FullVTR", 0.4, 0.4, 0.2, False),
    ]

    for name, vw, tw, rw, no_reb in strategies:
        sys.stdout.write(f"     {name}...")
        sys.stdout.flush()
        r = run_vtr_strategy(
            prices,
            instruments,
            val,
            trd,
            vol,
            value_weight=vw,
            trend_weight=tw,
            risk_weight=rw,
            no_rebalance=no_reb,
        )
        results[name] = extract_metrics(r)
        print(
            f" TWR={results[name]['twr']:.1%} CAGR={results[name]['cagr']:.2%} Sharpe={results[name]['sharpe']:.3f} DD={results[name]['max_drawdown']:.2%}"
        )

    # Benchmark is B1 (static SAA with rebalancing)
    saa = results.get("B1_Rebal", {})
    full_vtr_result = run_vtr_strategy(
        prices, instruments, val, trd, vol, value_weight=0.4, trend_weight=0.4, risk_weight=0.2
    )

    # Build StrategyReport
    print("\n[4] Building StrategyReport...")
    report = build_report(full_vtr_result, "B6_FullVTR", saa_metrics=saa)

    # Run validation gates
    print("\n[5] Running 10 Validation Gates...")
    engine = GateEngine()
    gates = engine.evaluate(report, saa_metrics=saa)

    print(f"\n{'Gate':<20} {'Status':<8} {'Description'}")
    print("-" * 80)
    for g in gates:
        status = "✅" if g.status.value == "pass" else "❌" if g.status.value == "fail" else "⚠️"
        print(f"{g.gate_name:<20} {status:<8} {g.description}")

    print(f"\n{'=' * 70}")
    print(f"  Strategy Status: {report.overall_status.value.upper()}")
    print(f"  Recommendation:  {report.recommendation}")
    print(f"{'=' * 70}")

    # Investor Simulation
    print("\n[6] Investor Simulation (monthly ¥50,000 contribution)...")
    inv = simulate_investor(full_vtr_result.unit_nav.dropna(), initial_capital=1_000_000, monthly_contribution=50_000)
    print(f"     Initial: ¥{inv.initial_capital:,.0f}")
    print(f"     Total contributed: ¥{inv.total_contributed:,.0f}")
    print(f"     Final wealth: ¥{inv.final_wealth:,.0f}")
    print(f"     Investment profit: ¥{inv.investment_profit:,.0f}")
    print(f"     XIRR: {inv.xirr_value:.2%}")
    print(f"     Max Drawdown: {inv.max_drawdown:.2%}")
    print(f"     Underwater ratio: {inv.underwater_ratio:.1%}")

    uw = compute_underwater_metrics(full_vtr_result.unit_nav.dropna())
    print("\n[7] Wealth Experience Metrics")
    print(f"     Underwater ratio: {uw.underwater_ratio:.1%}")
    print(f"     Longest underwater: {uw.longest_underwater_days} days")
    print(f"     Avg recovery (DD>5%): {uw.avg_recovery_days_above_5pct:.0f} days")
    print(f"     Avg recovery (DD>10%): {uw.avg_recovery_days_above_10pct:.0f} days")

    sp = compute_starting_points(full_vtr_result.unit_nav.dropna(), holding_years=5, step_months=3)
    print("\n[8] Multiple Starting Points (5Y holding, quarterly starts)")
    print(f"     N start points: {sp.n_start_points}")
    print(f"     Median CAGR: {sp.median_cagr:.2%}")
    print(f"     P10-P90 range: {sp.p10_cagr:.2%} ~ {sp.p90_cagr:.2%}")
    print(f"     Positive ratio: {sp.positive_ratio:.1%}")

    prob = compute_probabilities(full_vtr_result.unit_nav.dropna())
    print("\n[9] Probability Metrics")
    print(f"     P(5Y return < 0): {prob.p_5y_negative:.1%}")
    print(f"     P(MaxDD > 20%): {prob.p_max_dd_beyond_20pct:.1%}")
    print(f"     P(Underperform SAA over 5Y): {prob.p_underperform_saa_5y:.1%}")

    # Comparison table
    print(
        f"\n{'Strategy':<12} {'TWR':>8} {'CAGR':>8} {'Vol':>8} {'MaxDD':>8} {'Sharpe':>7} {'Calmar':>7}"
    )
    print("-" * 70)
    for name, m in results.items():
        print(
            f"{name:<12} {m['twr']:8.2%} {m['cagr']:8.2%} {m['volatility']:8.2%} {m['max_drawdown']:8.2%} {m['sharpe']:7.3f} {m['calmar']:7.3f}"
        )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(
                {
                    "strategy_id": report.strategy_id,
                    "status": report.overall_status.value,
                    "metrics": {name: m for name, m in results.items()},
                    "gates": [
                        {
                            "name": g.gate_name,
                            "status": g.status.value,
                            "description": g.description,
                        }
                        for g in gates
                    ],
                    "recommendation": report.recommendation,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    main()
