from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from wealth_os.domain.models import Instrument, PortfolioConstraints


@dataclass
class VTRAllocationPolicy:
    instruments: Mapping[str, Instrument]
    base_weights: pd.Series
    constraints: PortfolioConstraints
    cash_symbol: str
    value_weight: float = 0.40
    trend_weight: float = 0.40
    inverse_vol_weight: float = 0.20
    signal_strength: float = 0.30
    target_volatility: float = 0.10

    def generate_target_weights(
        self,
        date: pd.Timestamp,
        current_weights: pd.Series,
        signals: pd.DataFrame,
        volatility: pd.Series,
    ) -> pd.Series:
        symbols = self.base_weights.index
        value = signals.loc["value"].reindex(symbols).fillna(0.0)
        trend = signals.loc["trend"].reindex(symbols).fillna(0.0)
        vol = volatility.reindex(symbols).replace(0, np.nan)

        inverse_vol = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
        inverse_vol = inverse_vol / inverse_vol.mean(skipna=True)
        inverse_vol = inverse_vol.fillna(1.0).clip(0.25, 2.0)

        composite = self.value_weight * value + self.trend_weight * trend
        multiplier = (1.0 + self.signal_strength * np.tanh(composite)).clip(0.20, 1.80)
        multiplier = multiplier * (
            (1 - self.inverse_vol_weight) + self.inverse_vol_weight * inverse_vol
        )

        raw = self.base_weights * multiplier
        raw.loc[self.cash_symbol] = max(float(self.base_weights.get(self.cash_symbol, 0.0)), 0.0)
        raw = self._apply_bounds(raw)

        risky = raw.drop(self.cash_symbol, errors="ignore")
        estimated_portfolio_vol = float(
            np.sqrt(np.nansum((risky * vol.reindex(risky.index).fillna(0.0)) ** 2))
        )
        if estimated_portfolio_vol > 0:
            scale = min(1.0, self.target_volatility / estimated_portfolio_vol)
            risky *= scale
        raw.loc[risky.index] = risky
        raw.loc[self.cash_symbol] = max(0.0, 1.0 - risky.sum())
        raw = self._apply_group_bounds(raw)
        raw = self._limit_turnover(current_weights.reindex(symbols).fillna(0.0), raw)
        return self._normalize_with_cash(raw)

    def _apply_bounds(self, weights: pd.Series) -> pd.Series:
        out = weights.copy().fillna(0.0)
        for symbol in out.index:
            out.loc[symbol] = np.clip(
                out.loc[symbol],
                self.constraints.min_weights.get(symbol, 0.0),
                self.constraints.max_weights.get(symbol, 1.0),
            )
        return out

    def _apply_group_bounds(self, weights: pd.Series) -> pd.Series:
        out = weights.copy()
        for sleeve, (lower, upper) in self.constraints.sleeve_bounds.items():
            members = [s for s in out.index if self.instruments[s].sleeve == sleeve]
            if not members:
                continue
            current = float(out.loc[members].sum())
            if current > upper and current > 0:
                out.loc[members] *= upper / current
            elif current < lower:
                deficit = lower - current
                cash_available = max(0.0, out.get(self.cash_symbol, 0.0))
                add = min(deficit, cash_available)
                base = self.base_weights.loc[members]
                proportions = (
                    base / base.sum()
                    if base.sum() > 0
                    else pd.Series(1 / len(members), index=members)
                )
                out.loc[members] += proportions * add
                out.loc[self.cash_symbol] -= add
        return out

    def _limit_turnover(self, current: pd.Series, target: pd.Series) -> pd.Series:
        turnover = float((target - current).abs().sum() / 2.0)
        if turnover <= self.constraints.max_turnover or turnover == 0:
            return target
        fraction = self.constraints.max_turnover / turnover
        return current + fraction * (target - current)

    def _normalize_with_cash(self, weights: pd.Series) -> pd.Series:
        out = weights.clip(lower=0.0)
        non_cash = out.drop(self.cash_symbol, errors="ignore")
        if non_cash.sum() > 1:
            non_cash /= non_cash.sum()
        out.loc[non_cash.index] = non_cash
        out.loc[self.cash_symbol] = 1.0 - non_cash.sum()
        return out
