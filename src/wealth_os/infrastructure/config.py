from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore
from pydantic import BaseModel, Field


class AssetConfig(BaseModel):
    asset_class: str
    sleeve: str
    currency: str = "CNY"
    base_weight: float
    min_weight: float = 0.0
    max_weight: float = 1.0


class PortfolioConfig(BaseModel):
    base_currency: str = "CNY"
    initial_capital: float = 1_000_000
    initial_deployment_ratio: float = 0.65
    target_volatility: float = 0.10


class ModelConfig(BaseModel):
    value_weight: float = 0.40
    trend_weight: float = 0.40
    inverse_vol_weight: float = 0.20
    signal_strength: float = 0.30
    trend_periods: tuple[int, int, int] = (63, 126, 252)
    trend_ma_window: int = 200
    vol_window: int = 60
    valuation_lookback: int = 756


class CostsConfig(BaseModel):
    commission_bps: float = 1.0
    spread_bps: float = 5.0
    slippage_bps: float = 5.0
    market_impact_bps: float = 2.0
    sell_tax_bps: float = 5.0
    fx_bps: float = 5.0


class TriggerConfigModel(BaseModel):
    weight_drift: dict[str, float] = Field(default_factory=lambda: {"BTC": 0.005})
    signal_step: float = 0.2
    volatility_threshold_multiple: float = 1.25
    drawdown_levels: tuple[float, float, float, float] = (-0.05, -0.10, -0.15, -0.20)
    cooldown_days: int = 5
    min_trade_fraction: float = 0.005


class DemoConfig(BaseModel):
    seed: int = 7
    periods: int = 1500
    initial_capital: float = 1_000_000
    monthly_contribution: float = 20_000
    cash_annual_return: float = 0.02


class AppConfig(BaseModel):
    """Root configuration for Wealth OS."""

    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    assets: dict[str, AssetConfig] = Field(default_factory=dict)
    model: ModelConfig = Field(default_factory=ModelConfig)
    costs: CostsConfig = Field(default_factory=CostsConfig)
    triggers: TriggerConfigModel = Field(default_factory=TriggerConfigModel)
    demo: DemoConfig = Field(default_factory=DemoConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f)

        portfolio = PortfolioConfig(**data.get("portfolio", {}))
        assets = {name: AssetConfig(**cfg) for name, cfg in data.get("assets", {}).items()}

        return cls(portfolio=portfolio, assets=assets)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        return cls(**data)
