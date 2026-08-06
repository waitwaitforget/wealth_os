"""Risk factors: volatility, correlation, drawdown, downside metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wealth_os.factors.protocol import (
    FactorCategory,
    FactorDirection,
    FactorMeta,
)
from wealth_os.factors.registry import FactorRegistry


@FactorRegistry.register(name="volatility_20d")
class Volatility20dFactor:
    """20-day annualized realized volatility."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="volatility_20d",
            category=FactorCategory.RISK,
            description="20-day annualized realized volatility",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "volatility", "short_term"],
            parameters={"window": 20, "annualization": 252},
            output_range=(0.0, float("inf")),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        return ret.rolling(20, min_periods=10).std(ddof=0) * np.sqrt(252)


@FactorRegistry.register(name="volatility_60d")
class Volatility60dFactor:
    """60-day annualized realized volatility."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="volatility_60d",
            category=FactorCategory.RISK,
            description="60-day annualized realized volatility",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "volatility", "medium_term"],
            parameters={"window": 60, "annualization": 252},
            output_range=(0.0, float("inf")),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        return ret.rolling(60, min_periods=20).std(ddof=0) * np.sqrt(252)


@FactorRegistry.register(name="volatility_252d")
class Volatility252dFactor:
    """252-day annualized realized volatility."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="volatility_252d",
            category=FactorCategory.RISK,
            description="252-day annualized realized volatility",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "volatility", "long_term"],
            parameters={"window": 252, "annualization": 252},
            output_range=(0.0, float("inf")),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        return ret.rolling(252, min_periods=60).std(ddof=0) * np.sqrt(252)


@FactorRegistry.register(name="downside_volatility")
class DownsideVolatilityFactor:
    """Downside volatility — standard deviation of negative returns only."""

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="downside_volatility",
            category=FactorCategory.RISK,
            description="60-day downside (negative returns only) annualized volatility",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "volatility", "downside"],
            parameters={"window": 60, "annualization": 252},
            output_range=(0.0, float("inf")),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        downside = ret.where(ret < 0, 0.0)
        return downside.rolling(60, min_periods=20).std(ddof=0) * np.sqrt(252)


@FactorRegistry.register(name="max_drawdown")
class MaxDrawdownFactor:
    """Maximum drawdown from peak over rolling window."""

    def __init__(self, window: int = 252) -> None:
        self.window = window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="max_drawdown",
            category=FactorCategory.RISK,
            description="Maximum drawdown over rolling window",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "drawdown"],
            parameters={"window": self.window},
            output_range=(-1.0, 0.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=data.index, columns=data.columns, dtype=float)
        cummax = data.expanding().max()
        drawdown = data / cummax - 1.0
        for col in data.columns:
            dd_series = drawdown[col]
            rolling_min = dd_series.rolling(self.window, min_periods=1).min()
            result[col] = rolling_min
        return result


@FactorRegistry.register(name="rolling_correlation")
class RollingCorrelationFactor:
    """Rolling correlation between assets.  Returns (N, N) correlation matrix per row.

    For scoring purposes, returns the average pairwise correlation.
    """

    def __init__(self, window: int = 60) -> None:
        self.window = window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="rolling_correlation",
            category=FactorCategory.RISK,
            description="Rolling average pairwise correlation",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "correlation", "diversification"],
            parameters={"window": self.window},
            output_range=(-1.0, 1.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        corr = ret.rolling(self.window, min_periods=20).corr()
        if isinstance(corr.index, pd.MultiIndex):
            avg_corr = corr.groupby(level=0).apply(
                lambda x: x.values[np.triu_indices_from(x.values, k=1)].mean()
            )
            return pd.DataFrame({"avg_correlation": avg_corr}, index=data.index)
        return pd.DataFrame(0.0, index=data.index, columns=["avg_correlation"])


@FactorRegistry.register(name="historical_var")
class HistoricalVaRFactor:
    """Historical Value-at-Risk over rolling window."""

    def __init__(self, window: int = 252, confidence: float = 0.95) -> None:
        self.window = window
        self.confidence = confidence

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="historical_var",
            category=FactorCategory.RISK,
            description=f"Historical VaR ({self.confidence:.0%} confidence)",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "var", "tail_risk"],
            parameters={"window": self.window, "confidence": self.confidence},
            output_range=(float("-inf"), 0.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        result = pd.DataFrame(index=data.index, columns=data.columns, dtype=float)
        for col in data.columns:
            rolling_var = (
                ret[col].rolling(self.window, min_periods=60).quantile(1 - self.confidence)
            )
            result[col] = rolling_var
        return result
