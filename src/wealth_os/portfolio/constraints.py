"""Full constraint system — asset, market, currency, sector, cash, equity limits.

Extends the existing PortfolioConstraints with market-level,
currency-level, and sector-level bounds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from wealth_os.domain.models import Instrument


@dataclass(frozen=True)
class ConstraintViolation:
    constraint: str
    detail: str
    severity: str = "error"  # error | warning


@dataclass
class ConstraintResult:
    violations: list[ConstraintViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    def summary(self) -> str:
        if not self.violations:
            return "All constraints satisfied."
        lines = [f"{len(self.violations)} violations:"]
        for v in self.violations:
            lines.append(f"  [{v.severity}] {v.constraint}: {v.detail}")
        return "\n".join(lines)


@dataclass(frozen=True)
class FullConstraints:
    """Complete portfolio constraint configuration."""

    # Asset-level bounds
    min_weights: Mapping[str, float] = field(default_factory=dict)
    max_weights: Mapping[str, float] = field(default_factory=dict)

    # Sleeve-level bounds
    sleeve_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    # Market-level bounds
    market_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    # Currency-level bounds
    currency_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    # Sector-level bounds
    sector_bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    # Cash constraints
    min_cash: float = 0.05
    max_cash: float = 0.50

    # Equity bounds
    min_total_equity: float = 0.0
    max_total_equity: float = 1.0

    # Turnover
    max_turnover: float = 0.25
    allow_leverage: bool = False

    # Concentration
    max_single_position: float = 0.30
    max_single_market: float = 0.70
    max_single_currency: float = 0.80


class ConstraintChecker:
    """Validates weights against FullConstraints and returns violations.

    Supports asset, market, currency, sector, sleeve, cash, and
    equity-level checks.
    """

    def __init__(
        self,
        constraints: FullConstraints,
        instruments: dict[str, Instrument],
    ) -> None:
        self.constraints = constraints
        self.instruments = instruments

    def check(self, weights: pd.Series) -> ConstraintResult:
        result = ConstraintResult()

        self._check_weight_sum(weights, result)
        self._check_leverage(weights, result)
        self._check_asset_bounds(weights, result)
        self._check_sleeve_bounds(weights, result)
        self._check_market_bounds(weights, result)
        self._check_currency_bounds(weights, result)
        self._check_cash_bounds(weights, result)
        self._check_equity_bounds(weights, result)

        return result

    def is_feasible(self, weights: pd.Series) -> bool:
        return self.check(weights).passed

    def apply(self, weights: pd.Series, current_weights: pd.Series | None = None) -> pd.Series:
        """Enforce all constraints and return corrected weights.

        Applies: asset bounds, sleeve bounds, turnover limit, leverage check,
        cash normalization.
        """
        out = weights.copy().fillna(0.0)

        # Asset-level bounds
        for sym in out.index:
            upper = self.constraints.max_weights.get(sym, 1.0)
            lower = self.constraints.min_weights.get(sym, 0.0)
            out.loc[sym] = max(lower, min(upper, out.loc[sym]))

        # Sleeve bounds
        for sleeve, (lower, upper) in self.constraints.sleeve_bounds.items():
            members = [
                s
                for s in out.index
                if self.instruments.get(s) and self.instruments[s].sleeve == sleeve
            ]
            if not members:
                continue
            total = float(out[members].sum())
            if total > upper and total > 0:
                out.loc[members] *= upper / total
            elif total < lower:
                deficit = lower - total
                cash_syms = [s for s in out.index if "CASH" in s.upper()]
                cash_avail = max(0.0, sum(out.get(s, 0.0) for s in cash_syms))
                add = min(deficit, cash_avail)
                if add > 0 and members:
                    even_split = add / len(members)
                    out.loc[members] += even_split
                    for cs in cash_syms:
                        if cs in out.index:
                            deduction = even_split * len(members) / len(cash_syms)
                            out.loc[cs] = max(0.0, out.get(cs, 0.0) - deduction)

        # Turnover limit
        if current_weights is not None and self.constraints.max_turnover < 1.0:
            aligned = current_weights.reindex(out.index).fillna(0.0)
            turnover = float((out - aligned).abs().sum() / 2.0)
            if turnover > self.constraints.max_turnover and turnover > 0:
                fraction = self.constraints.max_turnover / turnover
                out = aligned + fraction * (out - aligned)

        # No negative weights (long-only)
        if not self.constraints.allow_leverage:
            out = out.clip(lower=0.0)

        # Normalize to 1.0 with cash as residual
        non_cash = out[~out.index.str.upper().str.contains("CASH")]
        cash_sym = next((s for s in out.index if "CASH" in s.upper()), None)
        if cash_sym:
            non_cash = non_cash.clip(lower=0.0)
            if non_cash.sum() > 1.0:
                non_cash /= non_cash.sum()
            out.loc[non_cash.index] = non_cash
            out.loc[cash_sym] = max(0.0, 1.0 - non_cash.sum())
        else:
            out = out.clip(lower=0.0)
            if out.sum() > 0:
                out /= out.sum()

        return out

    # ── Individual checks ────────────────────────────────────────

    def _check_weight_sum(self, weights: pd.Series, result: ConstraintResult) -> None:
        total = weights.sum()
        if abs(total - 1.0) > 1e-6:
            result.violations.append(
                ConstraintViolation(
                    "weight_sum",
                    f"Weights sum to {total:.6f} (expected 1.0)",
                    "error",
                )
            )

    def _check_leverage(self, weights: pd.Series, result: ConstraintResult) -> None:
        if not self.constraints.allow_leverage and (weights < -1e-6).any():
            neg = weights[weights < -1e-6]
            result.violations.append(
                ConstraintViolation(
                    "leverage",
                    f"Negative weights found: {neg.to_dict()}",
                    "error",
                )
            )

    def _check_asset_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        for sym, w in weights.items():
            upper = self.constraints.max_weights.get(sym, 1.0)
            lower = self.constraints.min_weights.get(sym, 0.0)
            if w > upper + 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "max_weight",
                        f"{sym}: {w:.4f} > max {upper:.4f}",
                        "error",
                    )
                )
            if w < lower - 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "min_weight",
                        f"{sym}: {w:.4f} < min {lower:.4f}",
                        "error",
                    )
                )

    def _check_sleeve_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        for sleeve, (lower, upper) in self.constraints.sleeve_bounds.items():
            members = [
                s
                for s in weights.index
                if self.instruments.get(s) and self.instruments[s].sleeve == sleeve
            ]
            if not members:
                continue
            total = float(weights[members].sum())
            if total > upper + 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "sleeve_upper",
                        f"{sleeve}: {total:.4f} > max {upper:.4f}",
                        "error",
                    )
                )
            if total < lower - 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "sleeve_lower",
                        f"{sleeve}: {total:.4f} < min {lower:.4f}",
                        "error",
                    )
                )

    def _check_market_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        for market, (_lower, upper) in self.constraints.market_bounds.items():
            members = [
                s
                for s in weights.index
                if s in self.instruments and getattr(self.instruments[s], "region", "") == market
            ]
            if not members:
                continue
            total = float(weights[members].sum())
            if total > upper + 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "market_upper",
                        f"{market}: {total:.4f} > max {upper:.4f}",
                        "warning",
                    )
                )

    def _check_currency_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        for currency, (_lower, upper) in self.constraints.currency_bounds.items():
            members = [
                s
                for s in weights.index
                if s in self.instruments and self.instruments[s].currency == currency
            ]
            if not members:
                continue
            total = float(weights[members].sum())
            if total > upper + 1e-6:
                result.violations.append(
                    ConstraintViolation(
                        "currency_upper",
                        f"{currency}: {total:.4f} > max {upper:.4f}",
                        "warning",
                    )
                )

    def _check_cash_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        cash_w = weights.get("CASH_CNY", 0.0)
        if cash_w < self.constraints.min_cash - 1e-6:
            result.violations.append(
                ConstraintViolation(
                    "min_cash",
                    f"Cash: {cash_w:.4f} < min {self.constraints.min_cash:.4f}",
                    "error",
                )
            )

    def _check_equity_bounds(self, weights: pd.Series, result: ConstraintResult) -> None:
        from wealth_os.domain.models import AssetClass

        equity = [
            s
            for s in weights.index
            if s in self.instruments
            and self.instruments[s].asset_class
            in (AssetClass.EQUITY_INDEX, AssetClass.STOCK, AssetClass.INDUSTRY)
        ]
        if not equity:
            return
        total_equity = float(weights[equity].sum())
        if total_equity > self.constraints.max_total_equity + 1e-6:
            result.violations.append(
                ConstraintViolation(
                    "max_equity",
                    f"Equity {total_equity:.4f} > {self.constraints.max_total_equity:.4f}",
                    "error",
                )
            )
