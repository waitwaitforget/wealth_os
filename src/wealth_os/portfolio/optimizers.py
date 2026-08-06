"""Portfolio optimizers — Risk Parity, Inverse Volatility, and unified interface.

Phase 1 optimizers:
- Inverse Volatility
- Risk Parity (naive: weight = 1/vol)
- VTR (existing, rules-based)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class InverseVolatilityOptimizer:
    """Weight assets inversely to their volatility.

    w_i = (1/σ_i) / Σ(1/σ_j)
    """

    min_weight: float = 0.01
    max_weight: float = 0.60
    include_cash: bool = False

    def optimize(
        self,
        volatility: pd.Series,
        cash_symbol: str = "",
    ) -> pd.Series:
        """Compute inverse-vol weights.

        Args:
            volatility: Annualized volatility per asset.
            cash_symbol: Excluded from risky pool if provided.

        Returns:
            Weights summing to 1.
        """
        vol = volatility.replace(0, np.nan).dropna()
        if cash_symbol and cash_symbol in vol.index:
            vol = vol.drop(cash_symbol)

        if vol.empty:
            return pd.Series(dtype=float)

        inv_vol = 1.0 / vol
        weights = inv_vol / inv_vol.sum()
        weights = weights.clip(self.min_weight, self.max_weight)
        weights = weights / weights.sum()

        if cash_symbol:
            result = pd.Series(0.0, index=volatility.index)
            result[weights.index] = weights
            result[cash_symbol] = 0.0
            return result

        return weights


@dataclass
class RiskParityOptimizer:
    """Naive risk parity: each asset contributes equally to portfolio risk.

    Uses iterative re-weighting:
        w_i = (target_risk / σ_i) / Σ(target_risk / σ_j)

    Simplified version: weight = 1/vol (first-order approximation).
    For full risk parity (with covariance), use cvxpy.
    """

    max_iterations: int = 10
    tolerance: float = 1e-6
    min_weight: float = 0.005

    def optimize(
        self,
        covariance: pd.DataFrame,
        target_risk_contribution: pd.Series | None = None,
    ) -> pd.Series:
        """Compute risk parity weights via iterative re-weighting.

        Args:
            covariance: Covariance matrix of returns.
            target_risk_contribution: Optional target risk per asset (default: equal).

        Returns:
            Weights summing to 1.
        """
        n = len(covariance)
        symbols = covariance.columns.tolist()
        weights = pd.Series(1.0 / n, index=symbols)

        if target_risk_contribution is None:
            target_risk_contribution = pd.Series(1.0 / n, index=symbols)

        cov_values = covariance.values

        for _ in range(self.max_iterations):
            portfolio_vol = np.sqrt(weights @ cov_values @ weights)

            if portfolio_vol < 1e-12:
                break

            marginal_risk = cov_values @ weights / portfolio_vol
            risk_contribution = weights * pd.Series(marginal_risk, index=symbols)

            rc_error = (
                (risk_contribution / risk_contribution.sum() - target_risk_contribution).abs().max()
            )
            if rc_error < self.tolerance:
                break

            # Update: w_i *= target_rc_i / actual_rc_i
            actual_rc_ratio = risk_contribution / max(risk_contribution.sum(), 1e-12)
            ratios = target_risk_contribution / actual_rc_ratio.replace(0, 1)
            weights = weights * ratios
            weights = weights.clip(self.min_weight, 1.0)
            weights = weights / weights.sum()

        return weights


@dataclass
class PortfolioOptimizer:
    """Unified portfolio optimizer combining signal adjustments + constraints.

    Strategy:
        1. Start with base (strategic) weights
        2. Apply signal multipliers (value × trend)
        3. Apply volatility scaling (risk parity or inverse vol)
        4. Enforce constraints
        5. Normalize to sum to 1 (with cash as residual)
    """

    base_weights: pd.Series
    cash_symbol: str

    value_weight: float = 0.40
    trend_weight: float = 0.40
    risk_weight: float = 0.20
    signal_strength: float = 0.30
    target_volatility: float = 0.10

    def compute_raw_weights(
        self,
        value_scores: pd.Series,
        trend_scores: pd.Series,
        volatility: pd.Series,
    ) -> pd.Series:
        """Step 1-2: Signal-adjusted raw weights before constraints."""
        symbols = [s for s in self.base_weights.index if s != self.cash_symbol]

        value = value_scores.reindex(symbols).fillna(0.0)
        trend = trend_scores.reindex(symbols).fillna(0.0)
        vol = volatility.reindex(symbols).replace(0, np.nan)

        # Inverse vol component
        inv_vol = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
        inv_vol = inv_vol / inv_vol.mean(skipna=True)
        inv_vol = inv_vol.fillna(1.0).clip(0.25, 2.0)

        # Composite signal
        composite = self.value_weight * value + self.trend_weight * trend
        multiplier = (1.0 + self.signal_strength * np.tanh(composite)).clip(0.20, 1.80)
        multiplier = multiplier * ((1 - self.risk_weight) + self.risk_weight * inv_vol)

        raw = self.base_weights.reindex(symbols).fillna(0.0) * multiplier

        # Cash weight
        raw[self.cash_symbol] = max(float(self.base_weights.get(self.cash_symbol, 0.0)), 0.0)

        # Risk scaling
        risky = raw.drop(self.cash_symbol, errors="ignore")
        est_vol = float(np.sqrt(np.nansum((risky * vol.reindex(risky.index).fillna(0.0)) ** 2)))
        if est_vol > 0:
            scale = min(1.0, self.target_volatility / est_vol)
            risky *= scale

        raw.loc[risky.index] = risky
        raw.loc[self.cash_symbol] = max(0.0, 1.0 - risky.sum())

        return raw
