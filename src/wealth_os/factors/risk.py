from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolatilityEstimator:
    window: int = 60
    annualization: int = 252

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        returns = prices.pct_change()
        return returns.rolling(self.window, min_periods=max(20, self.window // 3)).std(ddof=0) * np.sqrt(self.annualization)
