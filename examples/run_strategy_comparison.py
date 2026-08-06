"""Multi-strategy backtest comparison.

B0: Static strategic weights, no rebalance
B1: Static + quarterly rebalance
B2: Trend Only (trend signals × base weights)
B3: Value Only (value signals × base weights)
B4: Trend + Risk (trend signals + volatility scaling)
B5: Value + Trend (combined signals, no risk scaling)
B6: Full VTR (Value + Trend + Risk) + Dynamic Cash

Assets: CSI300, HSI, SP500*, NASDAQ100*, GOLD*, CASH_CNY
* = synthetic (API rate-limited)

Usage:
    python examples/run_strategy_comparison.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.performance import performance_summary
from wealth_os.backtest.costs import TransactionCostModel
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
from wealth_os.factors.risk import VolatilityEstimator
from wealth_os.factors.trend import TrendFactor
from wealth_os.factors.valuation import ValuationFactor
from wealth_os.infrastructure.data.repository import ParquetRepository

CASH_SYMBOL = "CASH_CNY"
INITIAL_CAPITAL = 1_000_000
DATA_DIR = "data"

ASSETS = ["CSI300", "HSI", "SP500", "NASDAQ100", "GOLD", CASH_SYMBOL]

STRATEGIC_WEIGHTS = pd.Series(
    {
        "CSI300": 0.20,
        "HSI": 0.12,
        "SP500": 0.28,
        "NASDAQ100": 0.10,
        "GOLD": 0.07,
        CASH_SYMBOL: 0.23,
    }
)

INSTRUMENT_DEFS = {
    "CSI300": ("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
    "HSI": ("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
    "SP500": ("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
    "NASDAQ100": ("NASDAQ100", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
    "GOLD": ("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
    CASH_SYMBOL: ("CASH_CNY", AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
}


def build_instruments(symbols: list[str]) -> dict[str, Instrument]:
    return {s: Instrument(*INSTRUMENT_DEFS[s]) for s in symbols if s in INSTRUMENT_DEFS}


def make_constraints() -> PortfolioConstraints:
    return PortfolioConstraints(
        max_weights={"GOLD": 0.15, "NASDAQ100": 0.25},
        min_weights={CASH_SYMBOL: 0.05},
        sleeve_bounds={Sleeve.CORE: (0.45, 0.90), Sleeve.ALTERNATIVE: (0.0, 0.10)},
        max_turnover=0.20,
    )


def load_prices() -> tuple[pd.DataFrame, str]:
    """Load all assets from repo. No synthetic fallback."""
    repo = ParquetRepository(root_dir=DATA_DIR)
    instruments = repo.load_instruments()
    if not instruments:
        raise RuntimeError("No data in repository. Run: python -m wealth_os.cli.ingest --all")

    instrument_ids = [i.instrument_id for i in instruments]
    loaded = repo.load_bars(instrument_ids, start=date(2018, 1, 1), end=date(2026, 8, 5))

    # Cash
    if CASH_SYMBOL not in loaded.columns:
        loaded[CASH_SYMBOL] = np.nan

    available = [c for c in loaded.columns if c in ASSETS]
    loaded = loaded[available]

    data_source = f"Real: {available}"
    return loaded, data_source


def make_factors(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    risky = prices.drop(columns=[CASH_SYMBOL], errors="ignore")

    valuation_metrics = {
        "earnings_yield": pd.DataFrame(
            0.06 + np.random.RandomState(1).uniform(-0.02, 0.02, size=risky.shape),
            index=risky.index,
            columns=risky.columns,
        ),
        "dividend_yield": pd.DataFrame(
            0.025 + np.random.RandomState(2).uniform(-0.005, 0.005, size=risky.shape),
            index=risky.index,
            columns=risky.columns,
        ),
    }

    valuation = (
        ValuationFactor({"earnings_yield": 0.7, "dividend_yield": 0.3}, lookback=756)
        .compute(valuation_metrics)
        .reindex(columns=prices.columns)
        .fillna(0.0)
    )
    trend = TrendFactor().compute(risky).reindex(columns=prices.columns).fillna(0.0)
    vol = VolatilityEstimator().compute(risky).reindex(columns=prices.columns).fillna(0.0)
    return valuation, trend, vol


def run_backtest(
    name: str,
    prices: pd.DataFrame,
    instruments: dict[str, Instrument],
    valuation: pd.DataFrame,
    trend: pd.DataFrame,
    vol: pd.DataFrame,
    value_weight: float = 0.0,
    trend_weight: float = 0.0,
    risk_weight: float = 0.0,
    signal_strength: float = 0.0,
    target_volatility: float = 0.15,
    periodic_rebalance_days: int = 0,
    no_rebalance: bool = False,
) -> BacktestResult:
    base = STRATEGIC_WEIGHTS.reindex(prices.columns).fillna(0.0)
    base = base / base.sum()

    constraints = make_constraints()
    allocator = VTRAllocationPolicy(
        instruments,
        base,
        constraints,
        CASH_SYMBOL,
        value_weight=value_weight,
        trend_weight=trend_weight,
        inverse_vol_weight=risk_weight,
        signal_strength=signal_strength,
        target_volatility=target_volatility,
    )

    trigger_config = TriggerConfig(weight_drift={"GOLD": 0.01})
    if no_rebalance:
        trigger_config = TriggerConfig(
            weight_drift=dict.fromkeys(prices.columns, 1.0),
            cooldown_days=99999,
        )
    elif periodic_rebalance_days > 0:
        trigger_config = TriggerConfig(
            weight_drift=dict.fromkeys(prices.columns, 0.005),
            cooldown_days=periodic_rebalance_days,
        )

    engine = NativeBacktestEngine(
        allocator=allocator,
        trigger_engine=RebalanceTriggerEngine(trigger_config),
        cost_model=TransactionCostModel(TransactionCostConfig(sell_tax_bps=3.0, fx_bps=3.0)),
        cash_symbol=CASH_SYMBOL,
        initial_capital=INITIAL_CAPITAL,
        initial_deployment_ratio=1.0,
    )

    contributions = pd.Series(0.0, index=prices.index)
    cash_returns = pd.Series((1.02 ** (1 / 252) - 1), index=prices.index)

    return engine.run(prices, valuation, trend, vol, contributions, cash_returns)


def extract_metrics(result: BacktestResult) -> dict[str, float]:
    perf = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    return {
        "TWR": perf["twr"],
        "CAGR": perf["annualized_return"],
        "Volatility": perf["annualized_volatility"],
        "Max DD": perf["max_drawdown"],
        "Sharpe": perf["sharpe"],
        "Sortino": perf["sortino"],
        "Calmar": perf.get("calmar", 0.0),
        "Orders": len(result.orders) if result.orders is not None else 0,
    }


def print_comparison(results: dict[str, dict[str, float]], source: str) -> None:
    print(f"\n{'=' * 90}")
    print("  STRATEGY COMPARISON")
    print("  Assets: CSI300, HSI, SP500, NASDAQ100, GOLD, CASH_CNY")
    print(f"  Data: {source}")
    print("  Period: 2018-01-02 → 2026-08-05")
    print(f"{'=' * 90}")

    header = f"{'Strategy':<12} {'TWR':>8} {'CAGR':>8} {'Vol':>8} {'MaxDD':>8} {'Sharpe':>7} {'Sortino':>7} {'Calmar':>7} {'Orders':>7}"
    print(header)
    print("-" * 90)

    for name, m in results.items():
        print(
            f"{name:<12} {m['TWR']:8.2%} {m['CAGR']:8.2%} {m['Volatility']:8.2%} "
            f"{m['Max DD']:8.2%} {m['Sharpe']:7.3f} {m['Sortino']:7.3f} "
            f"{m.get('Calmar', 0):7.3f} {m['Orders']:7d}"
        )

    print("-" * 90)

    # Find best per metric
    best_twr = max(results, key=lambda k: results[k]["TWR"])
    best_sharpe = max(results, key=lambda k: results[k]["Sharpe"])
    best_dd = max(results, key=lambda k: results[k]["Max DD"])
    print(f"\n  Best TWR:    {best_twr} ({results[best_twr]['TWR']:.2%})")
    print(f"  Best Sharpe: {best_sharpe} ({results[best_sharpe]['Sharpe']:.3f})")
    print(f"  Best Max DD: {best_dd} ({results[best_dd]['Max DD']:.2%})")

    # Add notes
    print("\n  NOTES:")
    print("  - CSI300/HSI: Real market data from AKShare")
    print("  - SP500/NASDAQ100/GOLD: Synthetic (API rate-limited)")
    print("  - Valuation factors use synthetic constants (no real PE data)")
    print("  - Trend factors use real price momentum")
    print("  - These results are for strategy COMPARISON only, not real performance")
    print(f"{'=' * 90}\n")


def main() -> None:
    print("Loading data...")
    prices, source = load_prices()
    print(f"  Data: {source}")
    print(f"  Range: {prices.index[0].date()} → {prices.index[-1].date()}")
    print(f"  Assets: {list(prices.columns)}")

    valuation, trend, vol = make_factors(prices)
    instruments = build_instruments(ASSETS)

    results: dict[str, dict[str, float]] = {}

    strategies = [
        ("B0 Static", 0.0, 0.0, 0.0, 0.0, 0.15, True),
        ("B1 Rebal", 0.0, 0.0, 0.0, 0.0, 0.15, False),
        ("B2 Trend", 0.0, 1.0, 0.0, 0.30, 0.15, False),
        ("B3 Value", 1.0, 0.0, 0.0, 0.30, 0.15, False),
        ("B4 Trend+R", 0.0, 0.80, 0.20, 0.35, 0.10, False),
        ("B5 Val+Trnd", 0.40, 0.40, 0.0, 0.30, 0.15, False),
        ("B6 FullVTR", 0.40, 0.40, 0.20, 0.30, 0.10, False),
    ]

    for name, vw, tw, rw, ss, tv, no_reb in strategies:
        print(f"  Running {name}...")
        result = run_backtest(
            name,
            prices,
            instruments,
            valuation,
            trend,
            vol,
            value_weight=vw,
            trend_weight=tw,
            risk_weight=rw,
            signal_strength=ss,
            target_volatility=tv,
            no_rebalance=no_reb,
        )
        results[name] = extract_metrics(result)

    print_comparison(results, source)


if __name__ == "__main__":
    main()
