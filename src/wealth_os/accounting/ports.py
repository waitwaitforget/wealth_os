"""Accounting port interfaces and value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class CashFlow:
    date: pd.Timestamp
    amount: float
    currency: str
    label: str


@dataclass(frozen=True)
class UnitNavSnapshot:
    date: pd.Timestamp
    nav: float
    units: float
    unit_nav: float


@runtime_checkable
class AccountingService(Protocol):
    def record_contribution(self, flow: CashFlow) -> UnitNavSnapshot: ...

    def compute_return(
        self,
        nav: pd.Series,
        cash_flows: pd.Series,
        initial_capital: float,
    ) -> dict[str, float]: ...
