"""Value factors: PE, PB, Dividend Yield, and composite scores."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from wealth_os.factors.common import rolling_zscore
from wealth_os.factors.protocol import (
    FactorCategory,
    FactorDirection,
    FactorMeta,
)
from wealth_os.factors.registry import FactorRegistry


@FactorRegistry.register(name="pe_earnings_yield")
class PEEarningsYieldFactor:
    """Earnings Yield = 1 / PE (trailing).

    Input: DataFrame of PE ratios (daily, per instrument).
    Output: Z-scored earnings yield (higher = cheaper).
    """

    def __init__(self, lookback: int = 756) -> None:
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="pe_earnings_yield",
            category=FactorCategory.VALUE,
            description="Earnings yield (1/PE) z-scored over rolling window",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "pe", "earnings_yield"],
            parameters={"lookback": self.lookback},
            input_fields=["pe_ratio"],
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ey = 1.0 / data.replace(0, np.nan)
        return rolling_zscore(ey.fillna(method="ffill"), self.lookback).clip(-3, 3)


@FactorRegistry.register(name="pb_inverse")
class PBInverseFactor:
    """Book-to-Price = 1 / PB. Higher B/P = cheaper."""

    def __init__(self, lookback: int = 756) -> None:
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="pb_inverse",
            category=FactorCategory.VALUE,
            description="Book-to-price (1/PB) z-scored",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "pb", "book_to_price"],
            parameters={"lookback": self.lookback},
            input_fields=["pb_ratio"],
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        bp = 1.0 / data.replace(0, np.nan)
        return rolling_zscore(bp.fillna(method="ffill"), self.lookback).clip(-3, 3)


@FactorRegistry.register(name="dividend_yield")
class DividendYieldFactor:
    """Dividend yield z-scored over rolling window."""

    def __init__(self, lookback: int = 756) -> None:
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="dividend_yield",
            category=FactorCategory.VALUE,
            description="Dividend yield z-scored over rolling window",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "dividend_yield", "income"],
            parameters={"lookback": self.lookback},
            input_fields=["dividend_yield"],
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        return rolling_zscore(data.fillna(method="ffill"), self.lookback).clip(-3, 3)


@FactorRegistry.register(name="valuation_composite")
class ValuationCompositeFactor:
    """Weighted composite of multiple valuation metrics.

    Each metric is z-scored individually, then combined by weight.
    Default: 70% earnings_yield + 30% dividend_yield.
    """

    def __init__(
        self,
        weights: Mapping[str, float] | None = None,
        lookback: int = 756,
    ) -> None:
        self.weights = weights or {"earnings_yield": 0.7, "dividend_yield": 0.3}
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="valuation_composite",
            category=FactorCategory.VALUE,
            description="Weighted composite of valuation metrics",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "composite"],
            parameters={
                "weights": dict(self.weights),
                "lookback": self.lookback,
            },
            input_fields=list(self.weights),
            output_range=(-3.0, 3.0),
        )

    def compute(self, metrics: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        total: pd.DataFrame | None = None
        used_weight = 0.0

        for name, weight in self.weights.items():
            if name not in metrics or weight == 0:
                continue
            score = rolling_zscore(metrics[name].fillna(method="ffill"), self.lookback)
            total = (
                score.mul(weight) if total is None else total.add(score.mul(weight), fill_value=0.0)
            )
            used_weight += abs(weight)

        if total is None or used_weight == 0:
            return pd.DataFrame(0.0, index=next(iter(metrics.values())).index)

        return (total / used_weight).clip(-3, 3)


@FactorRegistry.register(name="historical_percentile")
class HistoricalPercentileFactor:
    """Where current valuation stands relative to its own history.

    Input: raw valuation metric (PE, PB, etc.)
    Output: 0-1 percentile score (1 = expensive, normalize to range).
    """

    def __init__(self, lookback: int = 1260) -> None:
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="historical_percentile",
            category=FactorCategory.VALUE,
            description="Rolling historical percentile of valuation metric",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["value", "percentile", "relative_value"],
            parameters={"lookback": self.lookback},
            input_fields=["pe_ratio", "pb_ratio"],
            output_range=(0.0, 1.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=data.index, columns=data.columns, dtype=float)
        for col in data.columns:
            series = data[col].dropna()
            if len(series) < self.lookback // 2:
                continue
            rank = series.rolling(self.lookback, min_periods=60).rank(pct=True)
            result[col] = rank
        return result
