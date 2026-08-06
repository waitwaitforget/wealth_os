"""Trend factors: momentum, moving averages, trend strength, consensus."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wealth_os.factors.protocol import (
    FactorCategory,
    FactorDirection,
    FactorMeta,
)
from wealth_os.factors.registry import FactorRegistry


class _BaseMomentum:
    """Base for all momentum factors — computes returns, scales by vol."""

    def _momentum(
        self,
        prices: pd.DataFrame,
        period: int,
        clip: float = 3.0,
    ) -> pd.DataFrame:
        ret = prices.pct_change(period)
        vol = prices.pct_change().rolling(period, min_periods=period // 2).std(ddof=0)
        vol_scaled = np.sqrt(period)
        scale = vol.mul(vol_scaled).replace(0, np.nan)
        return ret.div(scale).clip(-clip, clip)


@FactorRegistry.register(name="momentum_3m")
class Momentum3MFactor(_BaseMomentum):
    """3-month (63 trading days) momentum, volatility-normalized."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="momentum_3m",
            category=FactorCategory.TREND,
            description="3-month momentum, volatility-normalized",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "momentum", "short_term"],
            parameters={"period": 63},
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        return self._momentum(data, period=63)


@FactorRegistry.register(name="momentum_6m")
class Momentum6MFactor(_BaseMomentum):
    """6-month (126 days) momentum."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="momentum_6m",
            category=FactorCategory.TREND,
            description="6-month momentum, volatility-normalized",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "momentum", "medium_term"],
            parameters={"period": 126},
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        return self._momentum(data, period=126)


@FactorRegistry.register(name="momentum_12m")
class Momentum12MFactor(_BaseMomentum):
    """12-month (252 days) momentum."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="momentum_12m",
            category=FactorCategory.TREND,
            description="12-month momentum, volatility-normalized",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "momentum", "long_term"],
            parameters={"period": 252},
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        return self._momentum(data, period=252)


@FactorRegistry.register(name="momentum_12m1m")
class Momentum12m1mFactor(_BaseMomentum):
    """12-month minus 1-month momentum (exclude most recent month)."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="momentum_12m1m",
            category=FactorCategory.TREND,
            description="12m-1m momentum (exclude recent month), volatility-normalized",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "momentum", "long_term"],
            parameters={"period_long": 252, "period_skip": 21},
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret_12m = data.pct_change(252)
        ret_1m = data.pct_change(21)
        ret = (1 + ret_12m) / (1 + ret_1m) - 1
        vol = data.pct_change().rolling(252, min_periods=60).std(ddof=0)
        return ret.div(vol.mul(np.sqrt(231)).replace(0, np.nan)).clip(-3, 3)


@FactorRegistry.register(name="ma_signal")
class MASignalFactor(_BaseMomentum):
    """Moving average deviation signal: (price / MA) - 1, scaled.

    Measures how far price is above/below its long-term moving average.
    """

    def __init__(self, window: int = 200) -> None:
        self.window = window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="ma_signal",
            category=FactorCategory.TREND,
            description="Price deviation from moving average, scaled to [-1,1]",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "ma", "regime"],
            parameters={"window": self.window},
            output_range=(-1.0, 1.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ma = data.rolling(self.window, min_periods=self.window // 2).mean()
        return (data / ma - 1.0).clip(-0.25, 0.25) * 4.0


@FactorRegistry.register(name="distance_from_high")
class DistanceFromHighFactor:
    """Distance from rolling high — measures drawdown/retracement."""

    def __init__(self, window: int = 252) -> None:
        self.window = window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="distance_from_high",
            category=FactorCategory.TREND,
            description="Distance from rolling high (pct drawdown)",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["trend", "drawdown", "retracement"],
            parameters={"window": self.window},
            output_range=(-1.0, 0.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        peak = data.rolling(self.window, min_periods=1).max()
        return data / peak.replace(0, np.nan) - 1.0


@FactorRegistry.register(name="trend_consensus")
class TrendConsensusFactor(_BaseMomentum):
    """Multi-period trend consensus: average of 3M/6M/12M momentum + MA."""

    def __init__(
        self,
        periods: tuple[int, ...] = (63, 126, 252),
        weights: tuple[float, ...] = (0.25, 0.35, 0.40),
        ma_window: int = 200,
    ) -> None:
        self.periods = periods
        self.weights = weights
        self.ma_window = ma_window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="trend_consensus",
            category=FactorCategory.TREND,
            description="Weighted multi-period momentum + MA signal composite",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "composite", "consensus"],
            parameters={
                "periods": list(self.periods),
                "weights": list(self.weights),
                "ma_window": self.ma_window,
            },
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        score = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        for period, weight in zip(self.periods, self.weights, strict=True):
            mom = self._momentum(data, period)
            score = score.add(mom.mul(weight), fill_value=0)

        ma = MASignalFactor(self.ma_window).compute(data)
        return score.add(ma.mul(0.15), fill_value=0).clip(-3, 3)
