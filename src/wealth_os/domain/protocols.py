from __future__ import annotations

from typing import Protocol

import pandas as pd

from .models import BacktestResult


class Factor(Protocol):
    def compute(self, data: pd.DataFrame) -> pd.DataFrame: ...


class AllocationPolicy(Protocol):
    def generate_target_weights(
        self,
        date: pd.Timestamp,
        current_weights: pd.Series,
        signals: pd.DataFrame,
        volatility: pd.Series,
    ) -> pd.Series: ...


class BacktestEngine(Protocol):
    def run(self, *args, **kwargs) -> BacktestResult: ...
