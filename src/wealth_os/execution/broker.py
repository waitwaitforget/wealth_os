"""Paper Broker — simulates order execution with realistic fills and costs.

Implements a zero-capital-risk execution environment that mimics
real broker behavior: lot sizes, price slippage, commission, and
partial fills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pandas as pd

from wealth_os.domain.models import Instrument


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class Order:
    order_id: str = ""
    date: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    notional: float = 0.0
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    fill_price: float = 0.0
    slippage_bps: float = 0.0
    commission: float = 0.0
    reason: str = ""

    @property
    def is_filled(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.PARTIAL)

    @property
    def fill_rate(self) -> float:
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity


@dataclass
class PaperBroker:
    """Simulated broker for paper trading.

    Simulates realistic fills with configurable slippage, commission,
    and minimum trade sizes.  Tracks cash balance and positions.
    """

    cash: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    commission_bps: float = 3.0
    slippage_model: str = "fixed"  # 'fixed' or 'volatility_proportional'
    slippage_bps: float = 5.0
    min_order_notional: float = 1000.0
    lot_sizes: dict[str, int] = field(default_factory=dict)
    order_history: list[Order] = field(default_factory=list)
    _order_counter: int = 0

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"ORD-{self._order_counter:06d}"

    # ── Order Planning ──────────────────────────────────────────

    def plan_orders(
        self,
        target_weights: pd.Series,
        current_positions: dict[str, float],
        prices: pd.Series,
        nav: float,
        instruments: dict[str, Instrument] | None = None,
    ) -> list[Order]:
        """Convert target weights to executable orders adjusted for constraints.

        Handles lot sizes, minimum notional, and cash constraints.
        """
        orders: list[Order] = []
        if nav <= 0:
            return orders

        current_value = sum(
            current_positions.get(sym, 0) * prices.get(sym, 0)
            for sym in set(current_positions) | set(target_weights.index)
        )

        available_cash = self.cash + current_value

        # Sell orders first
        for sym in current_positions:
            current_w = current_positions.get(sym, 0) * prices.get(sym, 0) / nav if nav > 0 else 0.0
            target_w = target_weights.get(sym, 0.0)
            delta_w = target_w - current_w

            if delta_w < -0.002:  # only sell if delta > 0.2%
                notional = abs(delta_w) * nav
                price = float(prices.get(sym, 0))
                if price <= 0:
                    continue
                qty = notional / price
                qty = self._round_to_lot(qty, sym)
                if qty > 0:
                    orders.append(
                        Order(
                            order_id=self._next_order_id(),
                            symbol=sym,
                            side=OrderSide.SELL,
                            quantity=qty,
                            notional=qty * price,
                            reason="rebalance",
                        )
                    )

        # Buy orders
        sell_proceeds = sum(abs(o.notional) for o in orders if o.side == OrderSide.SELL)
        buy_cash = available_cash + sell_proceeds

        for sym in target_weights.index:
            if sym in current_positions:
                current_w = (
                    current_positions.get(sym, 0) * prices.get(sym, 0) / nav if nav > 0 else 0.0
                )
            else:
                current_w = 0.0
            target_w = float(target_weights[sym])
            delta_w = target_w - current_w

            if delta_w > 0.002:
                notional = delta_w * nav
                notional = min(notional, buy_cash)
                price = float(prices.get(sym, 0))
                if price <= 0 or notional < self.min_order_notional:
                    continue
                qty = notional / price
                qty = self._round_to_lot(qty, sym)
                if qty > 0:
                    orders.append(
                        Order(
                            order_id=self._next_order_id(),
                            symbol=sym,
                            side=OrderSide.BUY,
                            quantity=qty,
                            notional=qty * price,
                            reason="rebalance",
                        )
                    )

        return orders

    def _round_to_lot(self, quantity: float, symbol: str) -> float:
        lot = self.lot_sizes.get(symbol, 1)
        if lot <= 0:
            return 0.0
        return max(0.0, float(int(quantity / lot) * lot))

    # ── Execution ───────────────────────────────────────────────

    def execute_market(
        self,
        order: Order,
        reference_price: float,
        volatility: float | None = None,
    ) -> Order:
        """Simulate a market order fill with slippage and commission."""
        if order.status != OrderStatus.APPROVED:
            return order

        slippage = self.slippage_bps
        if self.slippage_model == "volatility_proportional" and volatility is not None:
            slippage = max(1, slippage * volatility / 0.15)

        if order.side == OrderSide.BUY:
            fill_price = reference_price * (1 + slippage / 10000)
        else:
            fill_price = reference_price * (1 - slippage / 10000)

        order.filled_quantity = order.quantity
        order.fill_price = fill_price
        order.slippage_bps = slippage

        commission = order.quantity * fill_price * self.commission_bps / 10000
        order.commission = commission

        if order.side == OrderSide.BUY:
            self.cash -= order.quantity * fill_price + commission
            self.positions[order.symbol] = self.positions.get(order.symbol, 0) + order.quantity
        else:
            self.cash += order.quantity * fill_price - commission
            self.positions[order.symbol] = max(
                0, self.positions.get(order.symbol, 0) - order.quantity
            )

        order.status = OrderStatus.FILLED
        self.order_history.append(order)
        return order

    def execute_orders(
        self,
        orders: list[Order],
        prices: pd.Series,
        volatility: pd.Series | None = None,
        approve_all: bool = True,
    ) -> list[Order]:
        """Execute a batch of orders."""
        for o in orders:
            if approve_all:
                o.status = OrderStatus.APPROVED

            if o.symbol not in prices or prices[o.symbol] <= 0:
                o.status = OrderStatus.REJECTED
                continue

            vol = (
                float(volatility[o.symbol])
                if volatility is not None and o.symbol in volatility.index
                else None
            )
            self.execute_market(o, float(prices[o.symbol]), vol)

        return [o for o in orders if o.is_filled]

    # ── Summary ─────────────────────────────────────────────────

    def position_value(self, prices: pd.Series) -> float:
        return float(sum(self.positions.get(sym, 0) * prices.get(sym, 0) for sym in self.positions))

    def total_nav(self, prices: pd.Series) -> float:
        return float(self.cash + self.position_value(prices))

    def summary(self) -> dict[str, Any]:
        return {
            "cash": self.cash,
            "positions": dict(self.positions),
            "n_orders": len(self.order_history),
            "total_commission": sum(o.commission for o in self.order_history),
        }
