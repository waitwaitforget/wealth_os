from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from wealth_os.domain.models import BacktestResult, PortfolioConstraints


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


def validate_prices(prices: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not prices.index.is_monotonic_increasing:
        issues.append(ValidationIssue("error", "time_order", "Price index is not monotonic increasing"))
    if prices.index.has_duplicates:
        issues.append(ValidationIssue("error", "duplicate_time", "Price index contains duplicates"))
    if (prices <= 0).any().any():
        issues.append(ValidationIssue("error", "non_positive_price", "Prices must be positive"))
    if prices.isna().mean().max() > 0.10:
        issues.append(ValidationIssue("warning", "missing_data", "At least one asset has over 10% missing observations"))
    return issues


def validate_accounting(result: BacktestResult, tolerance: float = 1e-6) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    reconstructed = result.cash + result.positions_value.sum(axis=1)
    error = (reconstructed - result.nav).abs().max()
    if float(error) > tolerance:
        issues.append(ValidationIssue("error", "nav_identity", f"NAV identity failed; max error={error}"))
    reconstructed_unit = result.nav / result.units.replace(0, np.nan)
    unit_error = (reconstructed_unit - result.unit_nav).abs().max()
    if float(unit_error) > tolerance:
        issues.append(ValidationIssue("error", "unit_nav_identity", f"Unit NAV identity failed; max error={unit_error}"))
    if (result.cash < -tolerance).any():
        issues.append(ValidationIssue("error", "negative_cash", "Cash became negative"))
    return issues


def validate_weights(
    weights: pd.DataFrame,
    constraints: PortfolioConstraints,
    tolerance: float = 1e-6,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sums = weights.sum(axis=1)
    if ((sums - 1.0).abs() > tolerance).any():
        issues.append(ValidationIssue("error", "weight_sum", "Weights do not sum to one"))
    if (weights < -tolerance).any().any() and not constraints.allow_leverage:
        issues.append(ValidationIssue("error", "negative_weight", "Negative weights found in long-only portfolio"))
    for symbol, upper in constraints.max_weights.items():
        if symbol in weights and (weights[symbol] > upper + tolerance).any():
            issues.append(ValidationIssue("error", "max_weight", f"{symbol} exceeded max weight {upper}"))
    return issues


def validate_no_lookahead(
    factor_fn,
    data: pd.DataFrame,
    cutoff: pd.Timestamp,
    tolerance: float = 1e-12,
) -> list[ValidationIssue]:
    """Recompute after corrupting future data; pre-cutoff values must not change."""
    baseline = factor_fn(data.copy())
    corrupted = data.copy()
    corrupted.loc[corrupted.index > cutoff] = corrupted.loc[corrupted.index > cutoff].sample(frac=1.0, random_state=7).to_numpy()
    rerun = factor_fn(corrupted)
    left = baseline.loc[:cutoff]
    right = rerun.loc[:cutoff]
    diff = (left - right).abs().max().max()
    if float(diff) > tolerance:
        return [ValidationIssue("error", "lookahead", f"Historical factor values changed after future-data corruption; max diff={diff}")]
    return []
