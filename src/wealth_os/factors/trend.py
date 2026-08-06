from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .protocol import FactorCategory, FactorDirection, FactorMeta


@dataclass(frozen=True)
class TrendFactor:
    periods: tuple[int, ...] = (63, 126, 252)
    weights: tuple[float, ...] = (0.25, 0.35, 0.40)
    moving_average_window: int = 200

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="trend_legacy",
            category=FactorCategory.TREND,
            description="Multi-period momentum + MA signal composite (legacy)",
            version="0.1.0",
            direction=FactorDirection.POSITIVE,
            tags=["trend", "composite", "legacy"],
            parameters={
                "periods": list(self.periods),
                "weights": list(self.weights),
                "moving_average_window": self.moving_average_window,
            },
            output_range=(-3.0, 3.0),
        )

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        if len(self.periods) != len(self.weights):
            raise ValueError("periods and weights must have same length")
        score = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        for period, weight in zip(self.periods, self.weights, strict=True):
            momentum = prices.pct_change(period)
            scale = prices.pct_change().rolling(period).std(ddof=0) * np.sqrt(period)
            score = score.add(
                momentum.div(scale.replace(0, np.nan)).clip(-3, 3).mul(weight), fill_value=0
            )
        ma = prices.rolling(
            self.moving_average_window, min_periods=self.moving_average_window // 2
        ).mean()
        ma_state = (prices / ma - 1.0).clip(-0.25, 0.25) * 4.0
        return score.add(ma_state.mul(0.20), fill_value=0).clip(-3, 3)
