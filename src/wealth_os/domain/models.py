from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd


class AssetClass(StrEnum):
    EQUITY_INDEX = "equity_index"
    INDUSTRY = "industry"
    STOCK = "stock"
    BOND = "bond"
    GOLD = "gold"
    DIGITAL_ASSET = "digital_asset"
    CASH = "cash"
    CURRENCY = "currency"


class Sleeve(StrEnum):
    CORE = "core"
    SATELLITE = "satellite"
    ALTERNATIVE = "alternative"
    CASH = "cash"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: AssetClass
    sleeve: Sleeve
    currency: str
    region: str
    trading_calendar: str = "weekday"


@dataclass(frozen=True)
class PortfolioConstraints:
    min_weights: Mapping[str, float] = field(default_factory=dict)
    max_weights: Mapping[str, float] = field(default_factory=dict)
    sleeve_bounds: Mapping[Sleeve, tuple[float, float]] = field(default_factory=dict)
    currency_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    max_turnover: float = 0.25
    allow_leverage: bool = False


@dataclass(frozen=True)
class TransactionCostConfig:
    commission_bps: float = 1.0
    spread_bps: float = 2.0
    slippage_bps: float = 2.0
    market_impact_bps: float = 0.0
    sell_tax_bps: float = 0.0
    fx_bps: float = 0.0


@dataclass(frozen=True)
class TriggerConfig:
    weight_drift: Mapping[str, float] = field(default_factory=dict)
    default_weight_drift: float = 0.03
    signal_step: float = 0.20
    volatility_multiple: float = 1.20
    drawdown_levels: tuple[float, ...] = (-0.05, -0.10, -0.15, -0.20)
    cooldown_days: int = 5
    min_trade_fraction: float = 0.005


@dataclass
class BacktestResult:
    nav: pd.Series
    unit_nav: pd.Series
    units: pd.Series
    cash: pd.Series
    positions_value: pd.DataFrame
    actual_weights: pd.DataFrame
    target_weights: pd.DataFrame
    external_cash_flows: pd.Series
    transaction_costs: pd.Series
    turnover: pd.Series
    orders: pd.DataFrame
    diagnostics: dict[str, object] = field(default_factory=dict)
