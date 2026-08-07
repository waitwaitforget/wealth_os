"""Broker adapter protocol — interface for future real broker integration.

All broker implementations must implement this protocol for clean
swap between paper trading and live execution.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from wealth_os.execution.broker import Order


@runtime_checkable
class BrokerAdapter(Protocol):
    """Protocol for broker connectivity.

    Implementations handle the translation between Wealth OS order
    objects and broker-specific API calls.
    """

    @property
    def name(self) -> str: ...

    @property
    def is_live(self) -> bool: ...

    def get_positions(self) -> dict[str, float]: ...

    def get_cash_balance(self) -> float: ...

    def submit_orders(self, orders: list[Order]) -> list[Order]: ...

    def get_market_prices(self, symbols: list[str]) -> pd.Series: ...

    def check_connection(self) -> bool: ...


class DummyBrokerAdapter:
    """A no-op adapter that passes through to PaperBroker."""

    def __init__(self, paper_broker) -> None:
        self._broker = paper_broker

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def is_live(self) -> bool:
        return False

    def get_positions(self) -> dict[str, float]:
        return dict(self._broker.positions)

    def get_cash_balance(self) -> float:
        return float(self._broker.cash)

    def submit_orders(self, orders: list[Order]) -> list[Order]:
        return orders

    def get_market_prices(self, symbols: list[str]) -> pd.Series:
        return pd.Series(dtype=float)

    def check_connection(self) -> bool:
        return True
