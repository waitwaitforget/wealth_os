from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .protocol import FactorCategory, FactorDirection, FactorMeta


@dataclass(frozen=True)
class VolatilityEstimator:
    window: int = 60
    annualization: int = 252

    @property
    def meta(self) -> FactorMeta:
        return FactorMeta(
            name="volatility_legacy",
            category=FactorCategory.RISK,
            description="Annualized realized volatility (legacy)",
            version="0.1.0",
            direction=FactorDirection.NEGATIVE,
            tags=["risk", "volatility", "legacy"],
            parameters={"window": self.window, "annualization": self.annualization},
            output_range=(0.0, float("inf")),
        )

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        returns = prices.pct_change()
        return returns.rolling(self.window, min_periods=max(20, self.window // 3)).std(
            ddof=0
        ) * np.sqrt(self.annualization)
