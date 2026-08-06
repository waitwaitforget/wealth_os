"""Application-layer port interfaces.

These protocols define the contracts between use-case orchestrators
and infrastructure implementations.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd

from wealth_os.domain.models import BacktestResult


@runtime_checkable
class MarketDataProvider(Protocol):
    def load(self, symbols: list[str], start: str, end: str) -> pd.DataFrame: ...


@runtime_checkable
class FactorModel(Protocol):
    def compute(self, data: pd.DataFrame) -> pd.DataFrame: ...


@runtime_checkable
class AllocationPolicy(Protocol):
    def generate_target_weights(
        self,
        date: pd.Timestamp,
        current_weights: pd.Series,
        signals: pd.DataFrame,
        volatility: pd.Series,
    ) -> pd.Series: ...


@runtime_checkable
class BacktestEngine(Protocol):
    def run(self, *args: Any, **kwargs: Any) -> BacktestResult: ...


@runtime_checkable
class ExecutionBroker(Protocol):
    def send_orders(self, orders: pd.DataFrame) -> pd.DataFrame: ...
