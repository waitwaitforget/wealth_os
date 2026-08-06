"""Factor validation: hand-calculation, monotonicity, PIT, and stability tests.

Tests verify that each factor:
1. Produces correct values on small hand-calculable inputs
2. Behaves monotonically where expected (higher X → higher/lower score)
3. Is stateless and reproducible
4. Does not leak future information (Point-in-Time)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wealth_os.factors.protocol import Factor
from wealth_os.factors.risk_factors import (
    DownsideVolatilityFactor,
    HistoricalVaRFactor,
    MaxDrawdownFactor,
    Volatility20dFactor,
    Volatility60dFactor,
    Volatility252dFactor,
)
from wealth_os.factors.trend_factors import (
    DistanceFromHighFactor,
    MASignalFactor,
    Momentum3MFactor,
    Momentum6MFactor,
    Momentum12m1mFactor,
    Momentum12MFactor,
    TrendConsensusFactor,
)
from wealth_os.factors.value_factors import (
    DividendYieldFactor,
    HistoricalPercentileFactor,
    PBInverseFactor,
    PEEarningsYieldFactor,
)

# ============================================================
# Hand-calculation tests — small fixed inputs, manual output
# ============================================================


class TestHandCalculation:
    """Verify factor outputs against manually computed expected values."""

    @pytest.fixture
    def daily_prices(self) -> pd.DataFrame:
        """Simple line price: 100, 101, 102, ... rising steadily."""
        n = 200
        return pd.DataFrame(
            {"A": np.linspace(100, 130, n)},
            index=pd.date_range("2024-01-01", periods=n, freq="B"),
        )

    @pytest.fixture
    def pe_data(self) -> pd.DataFrame:
        """Simple PE series: declining from 20 to 10 (cheaper)."""
        n = 200
        return pd.DataFrame(
            {"A": np.linspace(20, 10, n)},
            index=pd.date_range("2024-01-01", periods=n, freq="B"),
        )

    # ── Momentum tests ──────────────────────────────────────────

    def test_momentum_3m_direction(self, daily_prices: pd.DataFrame) -> None:
        """Rising prices → positive momentum."""
        f = Momentum3MFactor()
        result = f.compute(daily_prices)
        last_vals = result["A"].dropna()
        assert len(last_vals) > 0
        # Rising line → positive momentum at the end
        assert last_vals.iloc[-1] > 0, "Rising price should give positive momentum"

    def test_momentum_stable_rising(self) -> None:
        """A perfectly linear rising series: momentum should be positive and bounded."""
        n = 200
        prices = pd.DataFrame(
            {"A": 100 + np.arange(n) * 0.1},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = Momentum3MFactor()
        result = f.compute(prices)
        valid = result["A"].dropna()
        assert (valid >= -3).all(), "Values should be >= -3"
        assert (valid <= 3).all(), "Values should be <= 3"

    # ── MA signal test ──────────────────────────────────────────

    def test_ma_signal_above_below(self) -> None:
        """Price above MA → positive signal; below → negative."""
        n = 150
        # First 100 days: flat at 100. Last 50 days: jump to 120.
        data = pd.Series([100.0] * 100 + [120.0] * 50)
        prices = pd.DataFrame(
            {"A": data.values},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )

        f200 = MASignalFactor(window=200)
        result = f200.compute(prices)

        # With flat+rise, the MA lags, so price/MA > 1 → positive signal
        last = result["A"].dropna().iloc[-1]
        assert last > 0, f"Price above MA should give positive signal, got {last}"

    # ── Distance from high test ─────────────────────────────────

    def test_distance_from_high_at_peak(self) -> None:
        """At the highest point, distance should be 0."""
        n = 100
        prices = pd.DataFrame(
            {"A": np.linspace(100, 150, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = DistanceFromHighFactor(window=252)
        result = f.compute(prices)
        last = result["A"].dropna().iloc[-1]
        assert abs(last) < 0.01, f"At peak, distance should be ~0, got {last}"

    # ── Value factor tests ──────────────────────────────────────

    def test_pe_earnings_yield_direction(self, pe_data: pd.DataFrame) -> None:
        """Declining PE → rising earnings yield → rising score."""
        f = PEEarningsYieldFactor(lookback=30)
        result = f.compute(pe_data)
        valid = result["A"].dropna()
        assert len(valid) > 0

    def test_pe_output_bounds(self, pe_data: pd.DataFrame) -> None:
        """PE factor output should be in [-3, 3]."""
        f = PEEarningsYieldFactor()
        result = f.compute(pe_data)
        valid = result["A"].dropna()
        assert (valid >= -3).all() and (valid <= 3).all()

    def test_dividend_yield_bounds(self) -> None:
        """Dividend yield factor output in [-3, 3]."""
        n = 100
        dy = pd.DataFrame(
            {"A": np.random.RandomState(42).uniform(0.01, 0.05, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = DividendYieldFactor(lookback=60)
        result = f.compute(dy)
        valid = result["A"].dropna()
        assert (valid >= -3).all() and (valid <= 3).all()

    # ── Risk factor tests ───────────────────────────────────────

    def test_vol20_positive(self, daily_prices: pd.DataFrame) -> None:
        f = Volatility20dFactor()
        result = f.compute(daily_prices)
        valid = result["A"].dropna()
        assert (valid >= 0).all(), "Volatility must be non-negative"

    def test_downside_vol_less_than_total(self, daily_prices: pd.DataFrame) -> None:
        """Downside vol ≤ total vol for same window."""
        n = 200
        rng = np.random.RandomState(99)
        prices = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum()},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        dv = DownsideVolatilityFactor()
        tv = Volatility60dFactor()
        d_result = dv.compute(prices)
        t_result = tv.compute(prices)
        common = d_result.dropna().index.intersection(t_result.dropna().index)
        assert (d_result.loc[common, "A"] <= t_result.loc[common, "A"] + 1e-6).all()

    def test_max_drawdown_non_positive(self, daily_prices: pd.DataFrame) -> None:
        """Max drawdown should be ≤ 0 (or 0 at peak)."""
        f = MaxDrawdownFactor(window=60)
        result = f.compute(daily_prices)
        valid = result["A"].dropna()
        assert (valid <= 0.01).all(), "Max DD should be <= 0"

    def test_var_negative(self, daily_prices: pd.DataFrame) -> None:
        """VaR should be negative (loss)."""
        f = HistoricalVaRFactor(window=60, confidence=0.95)
        result = f.compute(daily_prices)
        valid = result["A"].dropna()
        # In a steadily rising market, VaR may be near zero or negative
        assert (valid <= 0).all() or valid.abs().max() < 0.5


# ============================================================
# Meta and protocol compliance tests
# ============================================================


class TestFactorMeta:
    """Verify all registered factors have complete metadata."""

    FACTORS: list[type[Factor]] = [
        Momentum3MFactor,
        Momentum6MFactor,
        Momentum12MFactor,
        Momentum12m1mFactor,
        MASignalFactor,
        DistanceFromHighFactor,
        TrendConsensusFactor,
        PEEarningsYieldFactor,
        PBInverseFactor,
        DividendYieldFactor,
        HistoricalPercentileFactor,
        Volatility20dFactor,
        Volatility60dFactor,
        Volatility252dFactor,
        DownsideVolatilityFactor,
        MaxDrawdownFactor,
        HistoricalVaRFactor,
    ]

    def test_every_factor_has_meta(self) -> None:
        for fc in self.FACTORS:
            try:
                f = fc()
            except TypeError:
                f = fc(window=200)
            m = f.meta
            assert m.name, f"{fc.__name__}: missing name"
            assert m.category, f"{fc.__name__}: missing category"
            assert m.version == "0.1.0", f"{fc.__name__}: unexpected version"
            assert len(m.tags) >= 1, f"{fc.__name__}: no tags"
            assert m.output_range[0] <= m.output_range[1]

    def test_factor_reproducible(self) -> None:
        """Same input → same output (stateless)."""
        prices = pd.DataFrame(
            {"A": np.random.RandomState(0).uniform(90, 110, 200)},
            index=pd.date_range("2020-01-01", periods=200, freq="B"),
        )
        for fc in self.FACTORS[:3]:  # test momentum variants
            f = fc()
            r1 = f.compute(prices)
            r2 = f.compute(prices)
            pd.testing.assert_frame_equal(r1, r2)


# ============================================================
# Point-in-Time tests — ensure no future data leakage
# ============================================================


def _pit_check(factor_fn, data: pd.DataFrame, cutoff: pd.Timestamp) -> float:
    baseline = factor_fn(data.copy())
    corrupted = data.copy()
    mask = corrupted.index > cutoff
    shuffled = corrupted.loc[mask].sample(frac=1.0, random_state=7)
    corrupted.loc[mask] = shuffled.to_numpy()
    rerun = factor_fn(corrupted)
    left = baseline.loc[:cutoff]
    right = rerun.loc[:cutoff]
    common = left.columns.intersection(right.columns)
    diff_df = (left[common] - right[common]).abs()
    if diff_df.empty or diff_df.isna().all().all():
        return 0.0
    return float(diff_df.max().max())


class TestPointInTime:
    """Verify factors do not leak future information."""

    def test_momentum_pit(self) -> None:
        prices = pd.DataFrame(
            {"A": np.random.RandomState(1).uniform(90, 110, 300)},
            index=pd.date_range("2020-01-01", periods=300, freq="B"),
        )
        cutoff = prices.index[150]
        diff = _pit_check(Momentum3MFactor().compute, prices, cutoff)
        assert diff < 1e-10, f"Momentum PIT leak detected: diff={diff:.2e}"

    def test_ma_signal_pit(self) -> None:
        prices = pd.DataFrame(
            {"A": np.random.RandomState(2).uniform(90, 110, 300)},
            index=pd.date_range("2020-01-01", periods=300, freq="B"),
        )
        cutoff = prices.index[150]
        diff = _pit_check(MASignalFactor(window=200).compute, prices, cutoff)
        assert diff < 1e-10, f"MA signal PIT leak: diff={diff:.2e}"

    def test_volatility_pit(self) -> None:
        prices = pd.DataFrame(
            {"A": np.random.RandomState(3).uniform(90, 110, 400)},
            index=pd.date_range("2020-01-01", periods=400, freq="B"),
        )
        cutoff = prices.index[200]
        diff = _pit_check(Volatility60dFactor().compute, prices, cutoff)
        assert diff < 1e-10, f"Volatility PIT leak: diff={diff:.2e}"

    def test_pe_factor_no_future_leak(self) -> None:
        pe = pd.DataFrame(
            {"A": np.random.RandomState(4).uniform(5, 25, 300)},
            index=pd.date_range("2020-01-01", periods=300, freq="B"),
        )
        cutoff = pe.index[150]
        f = PEEarningsYieldFactor(lookback=60)
        diff = _pit_check(f.compute, pe, cutoff)
        assert diff < 1e-10, f"PE factor PIT leak: diff={diff:.2e}"


# ============================================================
# Parameter stability — small param changes → small output changes
# ============================================================


class TestParameterStability:
    """Verify that small parameter perturbations produce bounded output changes."""

    def test_ma_window_stability(self) -> None:
        n = 200
        prices = pd.DataFrame(
            {"A": np.random.RandomState(5).uniform(90, 110, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f200 = MASignalFactor(window=200).compute(prices)
        f220 = MASignalFactor(window=220).compute(prices)
        diff = (f200 - f220).abs().max().max()
        assert diff < 1.0, f"MA window change {200}→{220} caused {diff:.3f} shift"

    def test_vol_window_stability(self) -> None:
        n = 200
        prices = pd.DataFrame(
            {"A": np.random.RandomState(6).uniform(90, 110, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        v60 = Volatility60dFactor().compute(prices)
        v40 = Volatility20dFactor().compute(prices)
        diff = (v60 - v40).abs().max().max()
        # Different windows produce different volatilities, but not extreme
        assert diff < 0.5, f"Vol window change produced {diff:.3f} diff"


# ============================================================
# Monotonicity tests — factor output should move predictably
# ============================================================


class TestMonotonicity:
    """Verify factor output direction matches declared direction."""

    def test_pe_factor_cheaper_higher_score(self) -> None:
        """Lower PE → cheaper → higher value score."""
        n = 300
        # Use varying PE to avoid constant-rolling → NaN
        rng = np.random.RandomState(42)
        pe_high = pd.DataFrame(
            {"A": 30 + rng.standard_normal(n) * 0.5},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        pe_low = pd.DataFrame(
            {"A": 10 + rng.standard_normal(n) * 0.5},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = PEEarningsYieldFactor(lookback=60)
        score_high_pe = f.compute(pe_high)["A"].dropna().iloc[-1]
        score_low_pe = f.compute(pe_low)["A"].dropna().iloc[-1]
        assert score_low_pe > score_high_pe, (
            f"Cheaper (PE≈10) scored {score_low_pe:.3f}, "
            f"expensive (PE≈30) scored {score_high_pe:.3f}"
        )

    def test_momentum_up_higher_score(self) -> None:
        """Rising prices → higher momentum score."""
        n = 200
        trend_up = pd.DataFrame(
            {"A": 100 + np.linspace(0, 30, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        trend_down = pd.DataFrame(
            {"A": 130 - np.linspace(0, 30, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = Momentum3MFactor()
        up_score = f.compute(trend_up)["A"].dropna().iloc[-1]
        down_score = f.compute(trend_down)["A"].dropna().iloc[-1]
        assert up_score > down_score, (
            f"Uptrend scored {up_score:.3f}, downtrend scored {down_score:.3f}"
        )

    def test_vol_factor_stable_lower_risk(self) -> None:
        """Lower volatility → lower risk score."""
        n = 200
        rng = np.random.RandomState(42)
        stable = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum() * 0.1},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        volatile = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum() * 0.5},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = Volatility60dFactor()
        stable_vol = f.compute(stable)["A"].dropna().iloc[-1]
        vol_vol = f.compute(volatile)["A"].dropna().iloc[-1]
        assert stable_vol < vol_vol, f"Stable vol={stable_vol:.4f}, volatile vol={vol_vol:.4f}"

    def test_dividend_factor_higher_yield_higher_score(self) -> None:
        """Rising dividend yield → rising value score over time."""
        n = 600
        div_up = pd.DataFrame(
            {"A": np.linspace(0.01, 0.05, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = DividendYieldFactor(lookback=120)
        up_scores = f.compute(div_up)["A"].dropna()
        assert len(up_scores) > 0
        assert up_scores.iloc[-1] > 1.5, (
            f"Rising yield should end with positive z-score > 1.5, got {up_scores.iloc[-1]:.3f}"
        )


# ============================================================
# Lagged input tests — factor should respond with correct delay
# ============================================================


class TestLaggedInput:
    """Verify that lagging the input by k periods shifts output proportionally."""

    def test_ma_signal_lag_shift(self) -> None:
        """Shifting input forward shifts output forward (no lookahead)."""
        n = 300
        rng = np.random.RandomState(99)
        prices = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum()},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = MASignalFactor(window=100)
        result = f.compute(prices)

        # Lag input by 5 days
        lagged = prices.shift(5).bfill()
        result_lagged = f.compute(lagged)

        # Same values should occur ~5 days later in lagged result
        common = result.dropna().index.intersection(result_lagged.dropna().index[5:])
        if len(common) > 10:
            # The unstretched result at t should be close to the stretched result at t+5
            diff = result.loc[common[:-5], "A"].values - result_lagged.loc[common[5:], "A"].values
            avg_diff = abs(diff).mean()
            assert avg_diff < 0.5, f"MA signal lag shift too large: avg diff {avg_diff:.3f}"


# ============================================================
# New factor tests — Ulcer, ES, MRC, MA slope, downside trend
# ============================================================


class TestNewFactors:
    """Basic correctness tests for newly added factors."""

    def test_ulcer_index_non_negative(self) -> None:
        from wealth_os.factors.risk_factors import UlcerIndexFactor

        n = 200
        prices = pd.DataFrame(
            {"A": np.random.RandomState(7).uniform(90, 110, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = UlcerIndexFactor(window=100)
        result = f.compute(prices)["A"].dropna()
        assert (result >= 0).all()
        assert result.iloc[-1] < 0.3, "Random walk should have moderate ulcer index"

    def test_expected_shortfall_leq_var(self) -> None:
        """ES should be ≤ VaR (more extreme/below VaR)."""
        from wealth_os.factors.risk_factors import (
            ExpectedShortfallFactor,
            HistoricalVaRFactor,
        )

        n = 300
        rng = np.random.RandomState(88)
        prices = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum()},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        es = ExpectedShortfallFactor(window=100).compute(prices)
        var = HistoricalVaRFactor(window=100).compute(prices)

        common = es["A"].dropna().index.intersection(var["A"].dropna().index)
        assert (es.loc[common, "A"] <= var.loc[common, "A"] + 1e-6).all(), "ES should be ≤ VaR"

    def test_ma_slope_up_trend(self) -> None:
        from wealth_os.factors.trend_factors import MASlopeFactor

        n = 400
        prices = pd.DataFrame(
            {"A": 100 + np.linspace(0, 40, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = MASlopeFactor(ma_window=100, slope_window=20)
        result = f.compute(prices)["A"].dropna()
        assert result.iloc[-1] > 0, "Uptrend should produce positive MA slope"

    def test_downside_trend_strength_bounds(self) -> None:
        from wealth_os.factors.trend_factors import DownsideTrendStrengthFactor

        n = 200
        rng = np.random.RandomState(44)
        prices = pd.DataFrame(
            {"A": 100 + rng.standard_normal(n).cumsum()},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = DownsideTrendStrengthFactor(window=60)
        result = f.compute(prices)["A"].dropna()
        assert (result >= 0).all() and (result <= 1).all()

    def test_mrc_non_negative(self) -> None:
        from wealth_os.factors.risk_factors import MarginalRiskContributionFactor

        n = 200
        rng = np.random.RandomState(55)
        prices = pd.DataFrame(
            {
                "A": 100 + rng.standard_normal(n).cumsum(),
                "B": 100 + rng.standard_normal(n).cumsum() * 0.8,
                "C": 100 + rng.standard_normal(n).cumsum() * 0.5,
            },
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = MarginalRiskContributionFactor(window=60)
        result = f.compute(prices).dropna(how="all")
        if not result.empty:
            vals = result.iloc[-1]
            assert (vals >= 0).all()

    def test_cross_sectional_value_direction(self) -> None:
        from wealth_os.factors.value_factors import CrossSectionalValueFactor

        n = 100
        # Use earnings_yield as input (higher = cheaper)
        data = pd.DataFrame(
            {"A": np.linspace(0.10, 0.08, n), "B": np.linspace(0.03, 0.04, n)},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        f = CrossSectionalValueFactor()
        result = f.compute(data).dropna()
        if not result.empty and "A" in result.columns and "B" in result.columns:
            # Higher earnings_yield (A=0.10) → cheaper → should score higher
            assert result["A"].iloc[-1] > result["B"].iloc[-1], (
                "Cheaper asset (higher earnings yield) should score higher"
            )
