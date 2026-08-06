"""Index valuation tests — hand-calculation, aggregation, quality validation."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from wealth_os.domain.index_aggregation import (
    aggregate_dividend_yield,
    aggregate_pb,
    aggregate_pe,
    aggregate_ps,
    aggregate_roe,
    build_snapshot_from_constituents,
    build_snapshot_from_direct,
)
from wealth_os.domain.index_valuation import (
    AggregationMethod,
    FundamentalSnapshot,
    IndexConstituent,
    IndexValuationQualityReport,
)

# ── Small hand-calculable universe ────────────────────────────────


def _make_3stock_constituents() -> list[IndexConstituent]:
    return [
        IndexConstituent(
            index_id="TEST",
            constituent_id="A",
            weight=50.0,
            effective_date=date(2024, 1, 1),
        ),
        IndexConstituent(
            index_id="TEST",
            constituent_id="B",
            weight=30.0,
            effective_date=date(2024, 1, 1),
        ),
        IndexConstituent(
            index_id="TEST",
            constituent_id="C",
            weight=20.0,
            effective_date=date(2024, 1, 1),
        ),
    ]


def _make_3stock_fundamentals() -> dict[str, FundamentalSnapshot]:
    return {
        "A": FundamentalSnapshot(
            instrument_id="A",
            report_period=date(2024, 3, 31),
            filing_date=date(2024, 4, 15),
            market_cap=500,
            net_income_ttm=50,
            book_value=400,
            average_equity=350,
            revenue_ttm=600,
            dividend_ttm=10,
        ),
        "B": FundamentalSnapshot(
            instrument_id="B",
            report_period=date(2024, 3, 31),
            filing_date=date(2024, 4, 15),
            market_cap=300,
            net_income_ttm=15,
            book_value=250,
            average_equity=200,
            revenue_ttm=400,
            dividend_ttm=6,
        ),
        "C": FundamentalSnapshot(
            instrument_id="C",
            report_period=date(2024, 3, 31),
            filing_date=date(2024, 4, 15),
            market_cap=200,
            net_income_ttm=5,
            book_value=180,
            average_equity=150,
            revenue_ttm=300,
            dividend_ttm=3,
        ),
    }


class TestPEAggregation:
    """PE = sum(MarketCap) / sum(Earnings) — formula from section 8.1."""

    def test_hand_calculation(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        pe, valid_w, neg_w = aggregate_pe(
            constituents, fundamentals, "TEST", pd.Timestamp("2024-04-16")
        )

        # Hand calc:
        # MarketCap: 500 + 300 + 200 = 1000
        # Earnings: 50 + 15 + 5 = 70
        # PE = 1000/70 ≈ 14.2857
        assert pe is not None
        assert abs(pe - 14.2857) < 0.01, f"Expected ~14.29, got {pe}"
        assert abs(valid_w - 1.0) < 0.01
        assert neg_w == 0.0

    def test_negative_earnings_company(self) -> None:
        """A company with negative earnings still counts toward total earnings."""
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()
        # Change A to have large negative earnings
        fundamentals["A"] = FundamentalSnapshot(
            instrument_id="A",
            report_period=date(2024, 3, 31),
            filing_date=date(2024, 4, 15),
            market_cap=500,
            net_income_ttm=-30,
            book_value=400,
            average_equity=350,
            revenue_ttm=600,
        )

        pe, valid_w, neg_w = aggregate_pe(
            constituents, fundamentals, "TEST", pd.Timestamp("2024-04-16")
        )

        # Total earnings: -30 + 15 + 5 = -10 → PE should be None (negative total)
        assert pe is None, "PE should be None when total earnings <= 0"
        assert neg_w > 0, "Negative earnings weight should be tracked"

    def test_missing_fundamentals(self) -> None:
        """Missing fundamental data reduces valid_weight."""
        constituents = _make_3stock_constituents()
        fundamentals = {
            "A": FundamentalSnapshot(
                instrument_id="A",
                report_period=date(2024, 3, 31),
                filing_date=date(2024, 4, 15),
                market_cap=500,
                net_income_ttm=50,
            ),
            # B and C missing — no data
        }

        pe, valid_w, neg_w = aggregate_pe(
            constituents, fundamentals, "TEST", pd.Timestamp("2024-04-16")
        )

        assert pe is not None
        # PE = 500/50 = 10 (only from A)
        assert abs(pe - 10.0) < 0.01
        # valid_weight: only A (weight=50) out of total 100
        assert abs(valid_w - 0.50) < 0.01


class TestPBAggregation:
    """PB = sum(MarketCap) / sum(BookValue)."""

    def test_hand_calculation(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        pb, valid_w = aggregate_pb(constituents, fundamentals)

        # MarketCap: 1000, BookValue: 400+250+180 = 830
        # PB = 1000/830 ≈ 1.2048
        assert pb is not None
        assert abs(pb - 1.2048) < 0.01, f"Expected ~1.20, got {pb}"


class TestDividendYieldAggregation:
    """DivYield = sum(Dividend) / sum(MarketCap)."""

    def test_hand_calculation(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        dy = aggregate_dividend_yield(constituents, fundamentals)

        # Dividend: 10+6+3=19, MarketCap: 500+300+200=1000
        # Yield = 19/1000 = 0.019 = 1.9%
        assert dy is not None
        assert abs(dy - 0.019) < 0.001


class TestROEAggregation:
    """ROE = sum(NetIncome) / sum(AverageEquity)."""

    def test_hand_calculation(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        roe = aggregate_roe(constituents, fundamentals)

        # NetIncome: 50+15+5=70, AvgEquity: 350+200+150=700
        # ROE = 70/700 = 0.10 = 10%
        assert roe is not None
        assert abs(roe - 0.10) < 0.001


class TestPSAggregation:
    """PS = sum(MarketCap) / sum(Revenue)."""

    def test_hand_calculation(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        ps = aggregate_ps(constituents, fundamentals)

        # MCap: 1000, Revenue: 600+400+300=1300
        # PS = 1000/1300 ≈ 0.7692
        assert ps is not None
        assert abs(ps - 0.7692) < 0.01


class TestSnapshotBuilders:
    def test_direct_snapshot(self) -> None:
        snap = build_snapshot_from_direct(
            index_id="CSI300",
            observation_date=pd.Timestamp("2024-06-30"),
            pe_ttm=12.5,
            pb=1.3,
            dividend_yield=0.025,
            source="akshare",
        )

        assert snap.index_id == "CSI300"
        assert snap.pe_ttm == 12.5
        assert snap.pb == 1.3
        assert snap.dividend_yield == 0.025
        assert snap.earnings_yield == pytest.approx(1 / 12.5)
        assert snap.aggregation_method == AggregationMethod.DIRECT

    def test_constituent_snapshot(self) -> None:
        constituents = _make_3stock_constituents()
        fundamentals = _make_3stock_fundamentals()

        snap = build_snapshot_from_constituents(
            "TEST",
            pd.Timestamp("2024-04-16"),
            constituents,
            fundamentals,
        )

        assert snap.index_id == "TEST"
        assert snap.aggregation_method == AggregationMethod.CONSTITUENT_WEIGHTED
        assert snap.pe_ttm is not None
        assert snap.pb is not None
        assert snap.valid_weight == pytest.approx(1.0)
        assert snap.negative_earnings_weight == 0.0


class TestQualityReport:
    def test_perfect_match(self) -> None:
        report = IndexValuationQualityReport(
            index_id="CSI300",
            observation_date=pd.Timestamp("2024-06-30"),
            official_pe=12.5,
            calculated_pe=12.5,
            valid_weight=0.99,
        )
        report.compute_severity()
        assert report.severity == "PASS"
        assert report.pe_relative_error == 0.0

    def test_low_coverage_fails(self) -> None:
        report = IndexValuationQualityReport(
            index_id="CSI300",
            observation_date=pd.Timestamp("2024-06-30"),
            official_pe=12.5,
            calculated_pe=12.5,
            valid_weight=0.85,
        )
        report.compute_severity()
        assert report.severity == "FAIL"

    def test_large_pe_error(self) -> None:
        report = IndexValuationQualityReport(
            index_id="CSI300",
            observation_date=pd.Timestamp("2024-06-30"),
            official_pe=12.5,
            calculated_pe=15.0,
            valid_weight=0.98,
        )
        report.compute_severity()
        # 15/12.5 - 1 = 20% error → FAIL threshold (>8%)
        assert report.pe_relative_error == pytest.approx(0.20, abs=0.01)
        assert report.severity == "FAIL"
