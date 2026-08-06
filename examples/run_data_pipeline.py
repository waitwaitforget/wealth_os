"""Real-data pipeline demo.

Attempts to fetch real market data via AKShare/yfinance. Falls back
to synthetic data if providers are unavailable or fail.

Usage:
    python examples/run_data_pipeline.py [--data-dir data] [--synthetic]
"""

from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.performance import performance_summary, wealth_summary, xirr
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.backtest.native import NativeBacktestEngine
from wealth_os.data.synthetic import make_synthetic_market
from wealth_os.domain.data_models import (
    DataVersion,
    InstrumentMaster,
    Market,
    MarketDataBundle,
)
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

DEFAULT_INSTRUMENTS: dict[str, tuple[str, str, str, str, str]] = {
    "CSI300": ("CSI300", "沪深300", "equity_index", "SSE", "CNY"),
    "HSI": ("HSI", "恒生指数", "equity_index", "HKEX", "HKD"),
    "SP500": ("SP500", "标普500", "equity_index", "NYSE", "USD"),
    "GOLD": ("GOLD", "黄金", "gold", "FX", "USD"),
    "BOND": ("BOND", "债券", "bond", "SSE", "CNY"),
    "BTC": ("BTC", "比特币", "digital_asset", "CRYPTO", "USD"),
    "CASH_CNY": ("CASH_CNY", "人民币现金", "cash", "SSE", "CNY"),
}

SYMBOL_TO_INSTRUMENT_ID = {
    "CSI300": "CSI300",
    "HSI": "HSI",
    "SP500": "SP500",
    "GOLD": "GOLD",
    "BOND": "BOND",
    "BTC": "BTC",
    "CASH_CNY": "CASH_CNY",
}

# ── Real data fetch attempt ───────────────────────────────────────


def _try_fetch_real_data(
    data_dir: str,
    symbols: list[str],
) -> pd.DataFrame | None:
    try:
        from wealth_os.infrastructure.data.providers import AKShareProvider

        provider = AKShareProvider(cache_dir=f"{data_dir}/raw/akshare")
        return provider.fetch_bars(symbols, date(2018, 1, 1), date(2024, 12, 31))
    except Exception:
        return None


# ── Persist to repository ─────────────────────────────────────────


def _persist_to_repo(
    repo: ParquetRepository,
    prices: pd.DataFrame,
) -> tuple[DataVersion, pd.DataFrame]:
    instruments = []
    for sym, (inst_id, name, ac, mkt, cur) in DEFAULT_INSTRUMENTS.items():
        instruments.append(
            InstrumentMaster(
                instrument_id=inst_id,
                symbol=sym,
                name=name,
                asset_class=AssetClass(ac),
                market=Market(mkt),
                currency=cur,
            )
        )

    version = repo.create_version(instruments=instruments, bars=prices)
    return version, prices


# ── Main ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-data pipeline demo")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic data")
    args = parser.parse_args()

    data_dir = args.data_dir
    use_real = not args.synthetic

    cash_symbol = "CASH_CNY"
    repo = ParquetRepository(root_dir=data_dir)

    # ---- Fetch data ----
    prices = None
    data_source_label = "SYNTHETIC DEMO DATA (not real market performance)"

    if use_real:
        symbols = [
            s for s in DEFAULT_INSTRUMENTS if s != "CASH_CNY"
        ]
        real_prices = _try_fetch_real_data(data_dir, symbols)
        if real_prices is not None and not real_prices.empty:
            prices = real_prices
            data_source_label = "REAL MARKET DATA (AKShare + synthetic fallback)"
            _persist_to_repo(repo, prices)

    if prices is None:
        prices, valuation_metrics, contributions, cash_returns = make_synthetic_market()
        cash_returns = pd.Series(
            cash_returns.values, index=prices.index, name="CASH_CNY"
        )
        contributions = pd.Series(
            contributions.values, index=prices.index, name="contribution"
        )

    print(f"\n{'='*60}")
    print(f"  DATA TYPE: {data_source_label}")
    print(f"{'='*60}")

    # ---- Data health report ----
    bundle = MarketDataBundle(
        prices=prices,
        data_version=repo.get_latest_version(),
        description=f"Real-data demo: {len(prices.columns)} instruments",
    )
    validator = DataBundleValidator()
    health_report = validator.validate(bundle)
    print("\n" + health_report.summary())

    # ---- Build instruments ----
    instruments = {
        "CSI300": Instrument("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "HSI": Instrument("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
        "SP500": Instrument("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "GOLD": Instrument("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
        "BOND": Instrument("BOND", AssetClass.BOND, Sleeve.CORE, "CNY", "CN"),
        "BTC": Instrument(
            "BTC",
            AssetClass.DIGITAL_ASSET,
            Sleeve.ALTERNATIVE,
            "USD",
            "GLOBAL",
            "24x7",
        ),
        "CASH_CNY": Instrument("CASH_CNY", AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
    }
    base = pd.Series(
        {
            "CSI300": 0.18,
            "HSI": 0.10,
            "SP500": 0.25,
            "GOLD": 0.07,
            "BOND": 0.15,
            "BTC": 0.02,
            "CASH_CNY": 0.23,
        }
    )
    constraints = PortfolioConstraints(
        max_weights={"BTC": 0.03},
        min_weights={"CASH_CNY": 0.05},
        sleeve_bounds={Sleeve.CORE: (0.45, 0.90), Sleeve.ALTERNATIVE: (0.0, 0.05)},
        max_turnover=0.15,
    )

    # ---- Factors ----
    valuation_metrics_placeholder = {
        "earnings_yield": pd.DataFrame(
            0.06, index=prices.index, columns=prices.columns
        ),
        "dividend_yield": pd.DataFrame(
            0.025, index=prices.index, columns=prices.columns
        ),
    }
    valuation = ValuationFactor(
        {"earnings_yield": 0.7, "dividend_yield": 0.3}, lookback=756
    ).compute(valuation_metrics_placeholder)
    valuation = valuation.reindex(columns=base.index).fillna(0.0)
    trend = TrendFactor().compute(prices).reindex(columns=base.index).fillna(0.0)
    vol = (
        VolatilityEstimator().compute(prices).reindex(columns=base.index).fillna(0.0)
    )

    # ---- Backtest ----
    allocator = VTRAllocationPolicy(instruments, base, constraints, cash_symbol)
    contributions_series = pd.Series(0.0, index=prices.index)
    cash_ret_series = pd.Series((1.02 ** (1 / 252) - 1), index=prices.index)
    engine = NativeBacktestEngine(
        allocator=allocator,
        trigger_engine=RebalanceTriggerEngine(
            TriggerConfig(weight_drift={"BTC": 0.005})
        ),
        cost_model=TransactionCostModel(
            TransactionCostConfig(sell_tax_bps=5.0, fx_bps=5.0)
        ),
        cash_symbol=cash_symbol,
        initial_capital=1_000_000,
        initial_deployment_ratio=0.65,
    )
    result = engine.run(
        prices, valuation, trend, vol, contributions_series, cash_ret_series
    )

    # ---- Validation ----
    issues = (
        validate_prices(prices)
        + validate_accounting(result)
        + validate_weights(result.actual_weights, constraints)
    )
    print(ValidationReport(issues).summary())

    # ---- Performance ----
    _wealth = wealth_summary(
        result.nav, result.external_cash_flows, initial_capital=1_000_000
    )
    performance = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    investor_cash_flows = result.external_cash_flows.copy()
    investor_cash_flows.iloc[0] += 1_000_000
    money_weighted_return = xirr(
        investor_cash_flows, result.nav.iloc[-1], result.nav.index[-1]
    )

    print(f"\n=== Backtest ({data_source_label}) ===")
    print(
        f"Period: {performance['start_date'].date()} → {performance['end_date'].date()}"
    )
    print(f"TWR: {performance['twr']:.2%}")
    print(f"XIRR: {money_weighted_return:.2%}")
    print(
        f"Ann. Return: {performance['annualized_return']:.2%}  "
        f"Vol: {performance['annualized_volatility']:.2%}"
    )
    print(f"Max DD: {performance['max_drawdown']:.2%}")
    print(f"Sharpe: {performance['sharpe']:.3f}")
    print(f"Orders: {len(result.orders)}")


if __name__ == "__main__":
    main()
