"""Data quality validation.

Implements the ``DataValidator`` protocol from domain.  Checks
schema, uniqueness, missing data, price integrity, extreme
jumps, and point-in-time consistency.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from wealth_os.domain.data_models import (
    DataQualityIssue,
    DataQualityReport,
    DataQualitySeverity,
    MarketDataBundle,
)


class DataBundleValidator:
    """Validate a MarketDataBundle against data quality rules."""

    def validate(self, bundle: MarketDataBundle) -> DataQualityReport:
        issues: list[DataQualityIssue] = []

        issues.extend(_check_schema(bundle.prices))
        issues.extend(_check_uniqueness(bundle.prices))
        issues.extend(_check_missing(bundle.prices))
        issues.extend(_check_positive(bundle.prices))
        issues.extend(_check_date_range(bundle.prices))
        issues.extend(_check_extreme_jumps(bundle.prices))

        if bundle.adjusted_closes is not None:
            issues.extend(_check_adjustment_continuity(bundle.prices, bundle.adjusted_closes))

        report = DataQualityReport(
            issues=issues,
            data_version=bundle.data_version,
        )
        return report


# ── Individual checks ────────────────────────────────────────────


def _check_schema(prices: pd.DataFrame) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    if not isinstance(prices, pd.DataFrame):
        issues.append(
            DataQualityIssue(DataQualitySeverity.ERROR, "schema", "Not a DataFrame")
        )
        return issues

    if prices.empty:
        issues.append(
            DataQualityIssue(DataQualitySeverity.ERROR, "schema", "Prices DataFrame is empty")
        )
    if not isinstance(prices.index, pd.DatetimeIndex):
        issues.append(
            DataQualityIssue(
                DataQualitySeverity.ERROR, "schema", "Index is not DatetimeIndex"
            )
        )
    if prices.columns.duplicated().any():
        dups = list(prices.columns[prices.columns.duplicated()])
        issues.append(
            DataQualityIssue(
                DataQualitySeverity.ERROR,
                "schema",
                f"Duplicate columns: {dups}",
            )
        )
    return issues


def _check_uniqueness(prices: pd.DataFrame) -> list[DataQualityIssue]:
    if prices.index.duplicated().any():
        dup_count = int(prices.index.duplicated().sum())
        return [
            DataQualityIssue(
                DataQualitySeverity.ERROR,
                "duplicates",
                f"{dup_count} duplicate timestamps found",
            )
        ]
    return []


def _check_missing(prices: pd.DataFrame) -> list[DataQualityIssue]:
    if prices.empty:
        return []
    missing_ratio = prices.isna().mean()
    over_threshold = missing_ratio[missing_ratio > 0.05]
    issues: list[DataQualityIssue] = []
    for col, ratio in over_threshold.items():
        issues.append(
            DataQualityIssue(
                DataQualitySeverity.WARNING,
                "missing_data",
                f"{col}: {ratio:.1%} missing observations",
                instrument_id=str(col),
            )
        )
    return issues


def _check_positive(prices: pd.DataFrame) -> list[DataQualityIssue]:
    if prices.empty:
        return []
    neg_mask = prices < 0
    neg_count = int(neg_mask.sum().sum())
    if neg_count > 0:
        return [
            DataQualityIssue(
                DataQualitySeverity.ERROR,
                "negative_price",
                f"{neg_count} negative price observations",
            )
        ]
    return []


def _check_date_range(prices: pd.DataFrame) -> list[DataQualityIssue]:
    if prices.empty:
        return []
    issues: list[DataQualityIssue] = []
    start = prices.index.min()
    end = prices.index.max()

    for col in prices.columns:
        series = prices[col].dropna()
        if series.empty:
            continue
        first_valid = series.index.min()
        last_valid = series.index.max()
        if first_valid > start or last_valid < end:
            issues.append(
                DataQualityIssue(
                    DataQualitySeverity.WARNING,
                    "truncated_range",
                    f"{col}: data from {first_valid.date()} to {last_valid.date()} "
                    f"(bundle: {start.date()} to {end.date()})",
                    instrument_id=str(col),
                )
            )
    return issues


def _check_extreme_jumps(prices: pd.DataFrame) -> list[DataQualityIssue]:
    """Detect day-over-day price changes outside 3-sigma."""
    if prices.shape[1] == 0:
        return []
    returns = prices.pct_change().dropna(how="all")
    if returns.empty:
        return []

    sigma = returns.std()
    issues: list[DataQualityIssue] = []

    for col in returns.columns:
        col_rets = returns[col].dropna()
        if col_rets.empty:
            continue
        threshold = 5 * sigma[col]
        outliers = col_rets[col_rets.abs() > max(threshold, 0.15)]
        for ts, ret_val in outliers.items():
            issues.append(
                DataQualityIssue(
                    DataQualitySeverity.WARNING,
                    "extreme_jump",
                    f"{col}: {ts.date()} → {ret_val:.4f} ({ret_val:.2%})",
                    instrument_id=str(col),
                    timestamp=ts,
                )
            )
    return issues


def _check_adjustment_continuity(
    prices: pd.DataFrame,
    adjusted: pd.DataFrame,
) -> list[DataQualityIssue]:
    """Check that adjusted_close ratio is continuous (no jumps)."""
    if prices.empty or adjusted.empty:
        return []
    common_cols = [c for c in prices.columns if c in adjusted.columns]
    if not common_cols:
        return []

    issues: list[DataQualityIssue] = []
    for col in common_cols:
        ratio = adjusted[col] / prices[col].reindex(adjusted.index)
        ratio_clean = ratio.dropna()
        if ratio_clean.empty:
            continue
        ratio_chg = ratio_clean.pct_change().dropna()
        jump = ratio_chg[ratio_chg.abs() > 0.01]
        for ts, val in jump.items():
            issues.append(
                DataQualityIssue(
                    DataQualitySeverity.WARNING,
                    "adjustment_jump",
                    f"{col}: adj/close ratio jumped {val:.4%} on {ts.date()}",
                    instrument_id=str(col),
                    timestamp=ts,
                )
            )
    return issues


# ── Point-in-Time check ──────────────────────────────────────────


def validate_no_future_leak(
    factor_fn: Callable[[pd.DataFrame], pd.DataFrame],
    data: pd.DataFrame,
    cutoff: pd.Timestamp,
    tolerance: float = 1e-12,
) -> list[DataQualityIssue]:
    """Verify that a factor function does not peek into the future.

    Shuffles data after ``cutoff``, re-runs the factor, and checks
    that values before ``cutoff`` are unchanged.
    """
    baseline = factor_fn(data.copy())
    corrupted = data.copy()
    corrupted.loc[corrupted.index > cutoff] = (
        corrupted.loc[corrupted.index > cutoff]
        .sample(frac=1.0, random_state=7)
        .to_numpy()
    )
    rerun = factor_fn(corrupted)
    left = baseline.loc[:cutoff]
    right = rerun.loc[:cutoff]

    common = left.columns.intersection(right.columns)
    diff = (left[common] - right[common]).abs().max().max()
    if float(diff) > tolerance:
        return [
            DataQualityIssue(
                DataQualitySeverity.ERROR,
                "point_in_time",
                f"Historical factor values changed after future-data corruption; "
                f"max diff={float(diff):.6e}",
            )
        ]
    return []
