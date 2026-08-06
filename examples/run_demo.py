from __future__ import annotations

import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.analytics.performance import performance_summary, wealth_summary, xirr
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.backtest.native import NativeBacktestEngine
from wealth_os.data.synthetic import make_synthetic_market
from wealth_os.domain.models import (
    AssetClass, Instrument, PortfolioConstraints, Sleeve,
    TransactionCostConfig, TriggerConfig,
)
from wealth_os.factors.risk import VolatilityEstimator
from wealth_os.factors.trend import TrendFactor
from wealth_os.factors.valuation import ValuationFactor
from wealth_os.validation.checks import validate_accounting, validate_prices, validate_weights
from wealth_os.validation.report import ValidationReport


def main() -> None:
    prices, valuation_metrics, contributions, cash_returns = make_synthetic_market()
    cash_symbol = "CASH_CNY"
    instruments = {
        "CSI300": Instrument("CSI300", AssetClass.EQUITY_INDEX, Sleeve.CORE, "CNY", "CN"),
        "HSI": Instrument("HSI", AssetClass.EQUITY_INDEX, Sleeve.CORE, "HKD", "HK"),
        "SP500": Instrument("SP500", AssetClass.EQUITY_INDEX, Sleeve.CORE, "USD", "US"),
        "GOLD": Instrument("GOLD", AssetClass.GOLD, Sleeve.CORE, "USD", "GLOBAL"),
        "BOND": Instrument("BOND", AssetClass.BOND, Sleeve.CORE, "CNY", "CN"),
        "BTC": Instrument("BTC", AssetClass.DIGITAL_ASSET, Sleeve.ALTERNATIVE, "USD", "GLOBAL", "24x7"),
        cash_symbol: Instrument(cash_symbol, AssetClass.CASH, Sleeve.CASH, "CNY", "CN"),
    }
    base = pd.Series({"CSI300": .18, "HSI": .10, "SP500": .25, "GOLD": .07, "BOND": .15, "BTC": .02, cash_symbol: .23})
    constraints = PortfolioConstraints(
        max_weights={"BTC": .03},
        min_weights={cash_symbol: .05},
        sleeve_bounds={Sleeve.CORE: (.45, .90), Sleeve.ALTERNATIVE: (0.0, .05)},
        max_turnover=.15,
    )
    valuation = ValuationFactor({"earnings_yield": .7, "dividend_yield": .3}, lookback=756).compute(valuation_metrics)
    valuation = valuation.reindex(columns=base.index).fillna(0.0)
    trend = TrendFactor().compute(prices).reindex(columns=base.index).fillna(0.0)
    vol = VolatilityEstimator().compute(prices).reindex(columns=base.index).fillna(0.0)

    allocator = VTRAllocationPolicy(instruments, base, constraints, cash_symbol)
    engine = NativeBacktestEngine(
        allocator=allocator,
        trigger_engine=RebalanceTriggerEngine(TriggerConfig(weight_drift={"BTC": .005})),
        cost_model=TransactionCostModel(TransactionCostConfig(sell_tax_bps=5.0, fx_bps=5.0)),
        cash_symbol=cash_symbol,
        initial_capital=1_000_000,
        initial_deployment_ratio=.65,
    )
    result = engine.run(prices, valuation, trend, vol, contributions, cash_returns)
    issues = validate_prices(prices) + validate_accounting(result) + validate_weights(result.actual_weights, constraints)
    print(ValidationReport(issues).summary())

    wealth = wealth_summary(result.nav, result.external_cash_flows, initial_capital=1_000_000)
    performance = performance_summary(result.unit_nav, initial_unit_nav=1.0)
    investor_cash_flows = result.external_cash_flows.copy()
    investor_cash_flows.iloc[0] += 1_000_000
    money_weighted_return = xirr(investor_cash_flows, result.nav.iloc[-1], result.nav.index[-1])

    print("\n=== Backtest Information ===")
    print("Data type:                SYNTHETIC DEMO DATA (not real market performance)")
    print(f"Backtest start:           {performance['start_date'].date()}")
    print(f"Backtest end:             {performance['end_date'].date()}")
    print(f"Calendar duration:        {int(performance['calendar_days']):,} days ({performance['years']:.2f} years)")

    print("\n=== Wealth Summary ===")
    print(f"Initial capital:          {wealth['initial_capital']:,.2f}")
    print(f"Additional contributions: {wealth['additional_contributions']:,.2f}")
    print(f"Net invested capital:     {wealth['net_invested_capital']:,.2f}")
    print(f"Final portfolio value:    {wealth['final_portfolio_value']:,.2f}")
    print(f"Investment profit:        {wealth['investment_profit']:,.2f}")
    print(f"Simple return on capital: {wealth['simple_return_on_net_invested']:.2%}")

    print("\n=== Strategy Performance ===")
    print(f"Cumulative strategy return (TWR): {performance['twr']:.2%}")
    print(f"Annualized strategy return:       {performance['annualized_return']:.2%}")
    print(f"Annualized volatility:    {performance['annualized_volatility']:.2%}")
    print(f"Maximum drawdown:         {performance['max_drawdown']:.2%}")
    print(f"Sharpe ratio:             {performance['sharpe']:.3f}")
    print(f"Investor XIRR:            {money_weighted_return:.2%}")

    print("\nFinal weights:\n", result.actual_weights.iloc[-1].sort_values(ascending=False))
    print("Orders:", len(result.orders))


if __name__ == "__main__":
    main()
