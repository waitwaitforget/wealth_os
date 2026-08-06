from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from .common import rolling_zscore


@dataclass(frozen=True)
class ValuationFactor:
    weights: Mapping[str, float]
    lookback: int = 2520

    def compute(self, metrics: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        """Higher output means cheaper/more attractive.

        Expected keys can include earnings_yield, book_to_price, dividend_yield,
        cashflow_yield and equity_risk_premium. Metrics must already be aligned.
        """
        total: pd.DataFrame | None = None
        used_weight = 0.0
        for name, weight in self.weights.items():
            if name not in metrics or weight == 0:
                continue
            score = rolling_zscore(metrics[name], self.lookback)
            total = (
                score.mul(weight) if total is None else total.add(score.mul(weight), fill_value=0.0)
            )
            used_weight += abs(weight)
        if total is None or used_weight == 0:
            raise ValueError("No valuation metric matched configured weights")
        return total.div(used_weight).clip(-3, 3)
