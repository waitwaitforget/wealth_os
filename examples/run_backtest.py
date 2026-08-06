"""Run backtest with either saved real data or synthetic fallback.

Usage:
    python examples/run_backtest.py                          # auto-detect
    python examples/run_backtest.py --data-dir data          # from repo
    python examples/run_backtest.py --synthetic              # force synthetic
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.performance import performance_summary, wealth_summary, xirr
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.backtest.native import NativeBacktestEngine
from wealth_os.data.synthetic import make_synthetic_market
from wealth_os.domain.models import (
    AssetClass,
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
from wealth_os.validation.checks import validate_accounting, validate_prices, validate_weights
from wealth_os.validation.data_checks import DataBundleValidator
from wealth_os.validation.report import ValidationReport


def _load_from_repo(
    data_dir: str,
) -> tuple[pd.DataFrame, str] | None:
    repo = ParquetRepository(root_dir=data_dir)
    instruments = repo.load_instruments()
    if not instruments:
        return None

    instrument_ids = [i.instrument_id for i in instruments]
    prices = repo.load_bars(instrument_ids, start=date(2000, 1, 1), end=date(2030, 1, 1))
    if prices.empty:
        return None

    version = repo.get_latest_version()
    version_str = version.version_id if version else "unknown"
    return prices, version_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Wealth OS backtest")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic data")
    args = parser.parse_args()

    cash_symbol = "CASH_CNY"
    use_real = not args.synthetic

    # ---- Step 1: Load data ----
    prices = None
    source_label = "SYNTHETIC (not real performance)"
    valuation_metrics = None
    contributions = None
    cash_returns = None

    if use_real:
        loaded = _load_from_repo(args.data_dir)
        if loaded is not None:
            prices, version = loaded
            source_label = f"REAL MARKET (repo version: {version})"

    if prices is not None and not prices.empty:
        symbols_in_data = list(prices.columns)
    else:
        prices, valuation_metrics, contributions, cash_returns = make_synthetic_market()
        source_label = "SYNTHETIC (not real performance)"
        symbols_in_data = list(prices.columns)

    # ---- Step 2: Build instrument config ----
    symbol_configs: dict[str, dict] = {
        "CSI300": ("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "HSI": ("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
        "SP500": ("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "GOLD": ("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
        "BOND": ("BOND", AssetClass.BOND, Sleeve.CORE, "CNY", "CN"),
        "BTC": ("BTC", AssetClass.DIGITAL_ASSET, Sleeve.ALTERNATIVE, "USD", "GLOBAL", "24x7"),
    }

    # Map data symbols to config symbols
    instruments: dict[str, Instrument] = {}
    base_weights: dict[str, float] = {}
    data_symbols: list[str] = []

    for sym, (inst_id, ac, sl, cur, reg, *rest) in symbol_configs.items():
        if sym in symbols_in_data:
            cal = rest[0] if rest else "weekday"
            instruments[sym] = Instrument(inst_id, ac, sl, cur, reg, cal)
            data_symbols.append(sym)

    # Add cash
    instruments[cash_symbol] = Instrument(cash_symbol, AssetClass.CASH, Sleeve.CASH, "CNY", "CN")

    # Default weights (normalized if partial universe)
    default_w = {
        "CSI300": 0.18,
        "HSI": 0.10,
        "SP500": 0.25,
        "GOLD": 0.07,
        "BOND": 0.15,
        "BTC": 0.02,
    }
    total = sum(default_w.get(s, 0) for s in data_symbols)
    cash_w = 0.23 if total > 0.7 else 0.05
    for s in data_symbols:
        base_weights[s] = default_w.get(s, 0) / max(total, 0.01) * (1 - cash_w)
    base_weights[cash_symbol] = cash_w

    base = pd.Series(base_weights)

    constraints = PortfolioConstraints(
        max_weights={"BTC": 0.03},
        min_weights={cash_symbol: 0.05},
        sleeve_bounds={Sleeve.CORE: (0.45, 0.90), Sleeve.ALTERNATIVE: (0.0, 0.05)},
        max_turnover=0.15,
    )

    print(f"{'=' * 60}")
    print("  WEALTH OS BACKTEST")
    print(f"  Source: {source_label}")
    print(f"  Assets: {data_symbols}")
    print(f"  Period: {prices.index[0].date()} → {prices.index[-1].date()}")
    print(f"{'=' * 60}")

    # ---- Step 3: Data health check ----
    if use_real:
        from wealth_os.domain.data_models import MarketDataBundle

        bundle = MarketDataBundle(prices=prices[data_symbols])
        health = DataBundleValidator().validate(bundle)
        print(f"\n{health.summary()}")
        if health.error_count > 0:
            print("Aborting: data errors found.")
            sys.exit(1)

    # ---- Step 4: Factors ----
    prices_for_factor = prices[data_symbols].copy()

    if valuation_metrics is None:
        try:
            from wealth_os.infrastructure.data.valuation import ValuationProvider

            vp = ValuationProvider()
            real_metrics = vp.fetch_valuation_metrics(
                data_symbols,
                start=prices_for_factor.index[0].date(),
                end=prices_for_factor.index[-1].date(),
            )
            if real_metrics["earnings_yield"].empty:
                raise ValueError("Empty valuation data")

            valuation_metrics = {
                "earnings_yield": real_metrics["earnings_yield"].reindex(
                    index=prices_for_factor.index
                ),
                "dividend_yield": real_metrics["dividend_yield"].reindex(
                    index=prices_for_factor.index
                ),
            }
            print("\n[INFO] Using real valuation data from AKShare")
        except Exception:
            valuation_metrics = {
                "earnings_yield": pd.DataFrame(
                    0.06, index=prices_for_factor.index, columns=data_symbols
                ),
                "dividend_yield": pd.DataFrame(
                    0.025, index=prices_for_factor.index, columns=data_symbols
                ),
            }
            print("\n[WARN] Valuation metrics unavailable - using synthetic constants.")

    valuation = (
        ValuationFactor({"earnings_yield": 0.7, "dividend_yield": 0.3}, lookback=756)
        .compute(valuation_metrics)
        .reindex(columns=base.index)
        .fillna(0.0)
    )
    trend = TrendFactor().compute(prices_for_factor).reindex(columns=base.index).fillna(0.0)
    vol = VolatilityEstimator().compute(prices_for_factor).reindex(columns=base.index).fillna(0.0)

    # ---- Step 5: Backtest ----
    if contributions is None:
        contributions = pd.Series(0.0, index=prices.index)
    if cash_returns is None:
        cash_returns = pd.Series((1.02 ** (1 / 252) - 1), index=prices.index)

    allocator = VTRAllocationPolicy(instruments, base, constraints, cash_symbol)
    engine = NativeBacktestEngine(
        allocator=allocator,
        trigger_engine=RebalanceTriggerEngine(TriggerConfig(weight_drift={"BTC": 0.005})),
        cost_model=TransactionCostModel(TransactionCostConfig(sell_tax_bps=5.0, fx_bps=5.0)),
        cash_symbol=cash_symbol,
        initial_capital=1_000_000,
        initial_deployment_ratio=0.65,
    )
    result = engine.run(prices_for_factor, valuation, trend, vol, contributions, cash_returns)

    # ---- Step 6: Validation ----
    issues = (
        validate_prices(prices_for_factor)
        + validate_accounting(result)
        + validate_weights(result.actual_weights, constraints)
    )
    print(f"\n{ValidationReport(issues).summary()}")

    # ---- Step 7: Performance ----
    _wealth = wealth_summary(result.nav, result.external_cash_flows, initial_capital=1_000_000)
    performance = performance_summary(result.unit_nav, initial_unit_nav=1.0)

    investor_cf = result.external_cash_flows.copy()
    investor_cf.iloc[0] += 1_000_000
    irr = xirr(investor_cf, result.nav.iloc[-1], result.nav.index[-1])

    print("\n=== Performance ===")
    print(f"Strategy TWR:   {performance['twr']:.2%}")
    print(f"Ann. Return:    {performance['annualized_return']:.2%}")
    print(f"Volatility:     {performance['annualized_volatility']:.2%}")
    print(f"Max Drawdown:   {performance['max_drawdown']:.2%}")
    print(f"Sharpe:         {performance['sharpe']:.3f}")
    print(f"Investor XIRR:  {irr:.2%}")
    print(f"Orders:         {len(result.orders)}")

    final_weights = result.actual_weights.iloc[-1].sort_values(ascending=False)
    print(f"\nFinal weights:\n{final_weights.to_string()}")


if __name__ == "__main__":
    main()
