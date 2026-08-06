from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from wealth_os.allocation.policy import VTRAllocationPolicy
from wealth_os.allocation.triggers import RebalanceTriggerEngine
from wealth_os.backtest.costs import TransactionCostModel
from wealth_os.domain.models import BacktestResult
from wealth_os.portfolio.overlay import RiskOverlayStateMachine


@dataclass
class NativeBacktestEngine:
    allocator: VTRAllocationPolicy
    trigger_engine: RebalanceTriggerEngine
    cost_model: TransactionCostModel
    cash_symbol: str
    initial_capital: float
    initial_deployment_ratio: float = 0.70

    def run(
        self,
        prices: pd.DataFrame,
        value_scores: pd.DataFrame,
        trend_scores: pd.DataFrame,
        volatility: pd.DataFrame,
        external_cash_flows: pd.Series | None = None,
        cash_returns: pd.Series | None = None,
    ) -> BacktestResult:
        prices = prices.sort_index().ffill()
        symbols = list(self.allocator.base_weights.index)
        risky_symbols = [s for s in symbols if s != self.cash_symbol]
        prices = prices.reindex(columns=risky_symbols)
        external_cash_flows = (
            (
                external_cash_flows
                if external_cash_flows is not None
                else pd.Series(0.0, index=prices.index)
            )
            .reindex(prices.index)
            .fillna(0.0)
        )
        cash_returns = (
            (cash_returns if cash_returns is not None else pd.Series(0.0, index=prices.index))
            .reindex(prices.index)
            .fillna(0.0)
        )

        index = prices.index
        shares = pd.Series(0.0, index=risky_symbols)
        cash = self.initial_capital
        units = self.initial_capital
        unit_nav = 1.0
        target = pd.Series(0.0, index=symbols)
        target.loc[self.cash_symbol] = 1.0

        risk_overlay = RiskOverlayStateMachine(target_volatility=self.allocator.target_volatility)

        nav_records, unit_nav_records, unit_records, cash_records = [], [], [], []
        positions_records, actual_records, target_records = [], [], []
        cost_records, turnover_records, flow_records = [], [], []
        order_rows: list[dict[str, object]] = []
        peak_nav = self.initial_capital

        for step, date in enumerate(index):
            px = prices.loc[date]
            if step > 0:
                cash *= 1.0 + float(cash_returns.loc[date])

            float((shares * px).sum() + cash)
            flow = float(external_cash_flows.loc[date])
            if flow != 0:
                units += flow / unit_nav
                cash += flow

            nav = float((shares * px).sum() + cash)
            peak_nav = max(peak_nav, nav)
            drawdown = nav / peak_nav - 1.0
            actual = pd.Series(0.0, index=symbols)
            if nav > 0:
                actual.loc[risky_symbols] = shares * px / nav
                actual.loc[self.cash_symbol] = cash / nav

            signal_table = pd.DataFrame(
                {
                    s: [
                        value_scores.at[date, s] if s in value_scores.columns else 0.0,
                        trend_scores.at[date, s] if s in trend_scores.columns else 0.0,
                    ]
                    for s in symbols
                },
                index=["value", "trend"],
            )
            vol_today = volatility.loc[date].reindex(symbols).fillna(0.0)
            proposed = self.allocator.generate_target_weights(date, actual, signal_table, vol_today)

            # Risk overlay: scale risky assets based on drawdown state
            risk_mult = risk_overlay.update(drawdown)
            risky_proposed = proposed.drop(self.cash_symbol, errors="ignore")
            risky_proposed *= risk_mult
            proposed.loc[risky_proposed.index] = risky_proposed
            proposed.loc[self.cash_symbol] = max(0.0, 1.0 - risky_proposed.sum())

            rolling_returns = prices.pct_change().iloc[max(0, step - 59) : step + 1]
            portfolio_vol = 0.0
            if len(rolling_returns) > 10:
                aligned = actual.reindex(risky_symbols).fillna(0.0)
                portfolio_vol = float(
                    (rolling_returns.fillna(0.0) @ aligned).std(ddof=0) * np.sqrt(252)
                )

            composite = (
                signal_table.loc["value"].fillna(0) * self.allocator.value_weight
                + signal_table.loc["trend"].fillna(0) * self.allocator.trend_weight
            )
            decision = self.trigger_engine.evaluate(
                date,
                actual,
                proposed,
                composite,
                portfolio_vol,
                self.allocator.target_volatility,
                drawdown,
                flow,
            )

            day_cost = 0.0
            day_turnover = 0.0
            if step == 0:
                proposed = proposed.copy()
                risky = proposed.drop(self.cash_symbol) * self.initial_deployment_ratio
                proposed.loc[risky.index] = risky
                proposed.loc[self.cash_symbol] = 1.0 - risky.sum()
                decision = type(decision)(True, ("initial_deployment",))

            if decision.should_rebalance:
                desired_values = proposed.reindex(risky_symbols).fillna(0.0) * nav
                current_values = shares * px
                trades = desired_values - current_values
                min_notional = nav * self.trigger_engine.config.min_trade_fraction
                trades = trades.where(trades.abs() >= min_notional, 0.0)

                # Sell first, then buy using available cash.
                for symbol in trades[trades < 0].index:
                    notional = float(trades[symbol])
                    cost = self.cost_model.estimate(notional, is_sell=True)
                    shares[symbol] += notional / px[symbol]
                    cash -= notional + cost
                    day_cost += cost
                    day_turnover += abs(notional)
                    order_rows.append(
                        {
                            "date": date,
                            "symbol": symbol,
                            "notional": notional,
                            "cost": cost,
                            "reason": ";".join(decision.reasons),
                        }
                    )

                buys = trades[trades > 0]
                required = float(buys.sum())
                available = max(0.0, cash)
                scale = min(1.0, available / required) if required > 0 else 1.0
                for symbol in buys.index:
                    notional = float(buys[symbol] * scale)
                    cost = self.cost_model.estimate(notional, is_sell=False)
                    if notional + cost > cash:
                        notional = max(0.0, cash / (1 + (cost / notional if notional else 0)))
                        cost = self.cost_model.estimate(notional, is_sell=False)
                    shares[symbol] += notional / px[symbol]
                    cash -= notional + cost
                    day_cost += cost
                    day_turnover += abs(notional)
                    order_rows.append(
                        {
                            "date": date,
                            "symbol": symbol,
                            "notional": notional,
                            "cost": cost,
                            "reason": ";".join(decision.reasons),
                        }
                    )
                target = proposed

            nav = float((shares * px).sum() + cash)
            unit_nav = nav / units if units > 0 else np.nan
            peak_nav = max(peak_nav, nav)

            actual = pd.Series(0.0, index=symbols)
            if nav > 0:
                actual.loc[risky_symbols] = shares * px / nav
                actual.loc[self.cash_symbol] = cash / nav

            nav_records.append(nav)
            unit_nav_records.append(unit_nav)
            unit_records.append(units)
            cash_records.append(cash)
            positions_records.append((shares * px).rename(date))
            actual_records.append(actual.rename(date))
            target_records.append(target.rename(date))
            cost_records.append(day_cost)
            turnover_records.append(day_turnover / max(nav, 1e-12))
            flow_records.append(flow)

        orders = pd.DataFrame(order_rows)
        return BacktestResult(
            nav=pd.Series(nav_records, index=index, name="nav"),
            unit_nav=pd.Series(unit_nav_records, index=index, name="unit_nav"),
            units=pd.Series(unit_records, index=index, name="units"),
            cash=pd.Series(cash_records, index=index, name="cash"),
            positions_value=pd.DataFrame(positions_records, index=index).fillna(0.0),
            actual_weights=pd.DataFrame(actual_records, index=index).fillna(0.0),
            target_weights=pd.DataFrame(target_records, index=index).fillna(0.0),
            external_cash_flows=pd.Series(flow_records, index=index, name="external_cash_flow"),
            transaction_costs=pd.Series(cost_records, index=index, name="transaction_cost"),
            turnover=pd.Series(turnover_records, index=index, name="turnover"),
            orders=orders,
            diagnostics={
                "engine": "native",
                "initial_deployment_ratio": self.initial_deployment_ratio,
                "risk_overlay": risk_overlay.summary(),
            },
        )
