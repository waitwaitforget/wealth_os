"""Value factors: PE, PB, Dividend Yield, and composite scores."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from wealth_os.factors.common import robust_cross_sectional_zscore, rolling_zscore
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
        return rolling_zscore(ey.ffill(), self.lookback).clip(-3, 3)


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
        return rolling_zscore(bp.ffill(), self.lookback).clip(-3, 3)


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
        return rolling_zscore(data.ffill(), self.lookback).clip(-3, 3)


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
            score = rolling_zscore(metrics[name].ffill(), self.lookback)
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


@FactorRegistry.register(name="cross_sectional_value")
class CrossSectionalValueFactor:
    """Cross-sectional valuation z-score: compare each asset's valuation
    relative to peers at each point in time.

    Uses robust median-MAD z-score for outlier resistance.
    """

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="cross_sectional_value",
            category=FactorCategory.VALUE,
            description="Cross-sectional (peer-relative) valuation z-score",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "cross_sectional", "relative_value"],
            parameters={},
            input_fields=["pe_ratio", "pb_ratio", "earnings_yield"],
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        return robust_cross_sectional_zscore(data.dropna(how="all")).clip(-3, 3)


@FactorRegistry.register(name="equity_risk_premium")
class EquityRiskPremiumFactor:
    """ERP = Earnings Yield - Risk-Free Rate.

    Higher ERP means stocks are cheaper relative to bonds.  The
    risk-free rate is provided as a separate DataFrame or Series.
    """

    def __init__(self, lookback: int = 756) -> None:
        self.lookback = lookback

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="equity_risk_premium",
            category=FactorCategory.VALUE,
            description="Equity Risk Premium = earnings_yield - risk_free_rate, z-scored",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "erp", "macro", "risk_premium"],
            parameters={"lookback": self.lookback},
            input_fields=["earnings_yield", "risk_free_rate"],
            output_range=(-3.0, 3.0),
        )

    def compute(
        self,
        data: pd.DataFrame,
        risk_free_rate: pd.Series | None = None,
    ) -> pd.DataFrame:
        """Compute ERP z-score.

        Args:
            data: DataFrame of earnings_yield per asset
            risk_free_rate: Series of risk-free rate (e.g., 10Y bond yield)
        """
        if risk_free_rate is None:
            risk_free_rate = pd.Series(0.025, index=data.index)
        risk_free_aligned = risk_free_rate.reindex(data.index).ffill()
        erp = data.sub(risk_free_aligned, axis=0)
        return rolling_zscore(erp.ffill(), self.lookback).clip(-3, 3)


@FactorRegistry.register(name="cape_approximation")
class CAPEApproximationFactor:
    """Approximate CAPE (Shiller PE) using long-term smoothing.

    Uses a 5-year (1260-day) rolling average of earnings_yield to
    approximate cyclically-adjusted earnings.  Not a true CAPE
    (which uses 10-year real earnings) but provides a long-term
    smoothed valuation signal.
    """

    def __init__(self, smoothing_window: int = 1260) -> None:
        self.smoothing_window = smoothing_window

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="cape_approximation",
            category=FactorCategory.VALUE,
            description="Approximate CAPE via 5-year smoothed earnings yield, z-scored",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["value", "cape", "long_term", "cyclical"],
            parameters={"smoothing_window": self.smoothing_window},
            input_fields=["earnings_yield"],
            output_range=(-3.0, 3.0),
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        smoothed = data.ffill().rolling(self.smoothing_window, min_periods=252).mean()
        return rolling_zscore(smoothed, self.smoothing_window).clip(-3, 3)
