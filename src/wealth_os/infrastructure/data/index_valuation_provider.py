"""Index valuation provider — fetches and validates index-level PE/PB/Dividend.

Implements both direct-fetch and quality reconciliation as specified in
the index valuation handoff document.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from wealth_os.domain.index_aggregation import build_snapshot_from_direct
from wealth_os.domain.index_valuation import (
    IndexValuationQualityReport,
    IndexValuationSnapshot,
)

# Known index definitions
INDEX_DEFINITIONS: dict[str, dict] = {
    "CSI300": {
        "provider": "CSI",
        "akshare_pe_name": "沪深300",
        "csindex_code": "000300",
    },
    "CSI500": {
        "provider": "CSI",
        "akshare_pe_name": "中证500",
        "csindex_code": "000905",
    },
    "DIVIDEND": {
        "provider": "CSI",
        "akshare_pe_name": "上证红利",
        "csindex_code": "000922",
    },
}


class IndexValuationProvider:
    """Fetch index valuation data and produce quality-annotated snapshots.

    Currently supports direct-fetch from AKShare.  Constituent-level
    aggregation (Sprint C) to be added when Tushare token is available.
    """

    def __init__(self) -> None:
        pass

    def fetch_snapshot(
        self,
        index_id: str,
        observation_date: date,
    ) -> IndexValuationSnapshot | None:
        """Fetch a single-day valuation snapshot for an index."""
        return (
            self.fetch_snapshot_range(index_id, observation_date, observation_date)[0]
            if self.fetch_snapshot_range(index_id, observation_date, observation_date)
            else None
        )

    def fetch_snapshot_range(
        self,
        index_id: str,
        start: date,
        end: date,
    ) -> list[IndexValuationSnapshot]:
        """Fetch valuation snapshots for a date range."""
        info = INDEX_DEFINITIONS.get(index_id)
        if info is None:
            return []

        snapshots: list[IndexValuationSnapshot] = []

        # Fetch PE from AKShare
        pe_data = self._fetch_pe_series(index_id, info["akshare_pe_name"], start, end)
        # Fetch PB from AKShare
        pb_data = self._fetch_pb_series(index_id, info["akshare_pe_name"], start, end)
        # Fetch dividend yield from CSIndex
        div_data = self._fetch_dividend_series(index_id, info["csindex_code"], start, end)

        # Build snapshots for each date where we have at least PE data
        dates = pe_data.dropna().index if not pe_data.empty else pd.DatetimeIndex([])
        for ts in dates:
            pe_val = float(pe_data.get(ts, None))
            pb_val = float(pb_data.get(ts, None)) if ts in pb_data.index else None
            div_val = float(div_data.get(ts, None)) if ts in div_data.index else None

            if pd.isna(pe_val):
                continue

            snapshot = build_snapshot_from_direct(
                index_id=index_id,
                observation_date=ts,
                pe_ttm=pe_val if not pd.isna(pe_val) else None,
                pb=pb_val if pb_val is not None and not pd.isna(pb_val) else None,
                dividend_yield=div_val if div_val is not None and not pd.isna(div_val) else None,
                source="akshare",
            )
            snapshots.append(snapshot)

        return snapshots

    def fetch_quality_report(
        self,
        index_id: str,
        observation_date: date,
    ) -> IndexValuationQualityReport | None:
        """Generate a quality report comparing official vs calculated values."""
        info = INDEX_DEFINITIONS.get(index_id)
        if info is None:
            return None

        official = self.fetch_snapshot(index_id, observation_date)
        if official is None:
            return None

        report = IndexValuationQualityReport(
            index_id=index_id,
            observation_date=pd.Timestamp(observation_date),
        )

        # For direct-fetch mode, the "calculated" value IS the official value
        # (since we're fetching from the index provider directly)
        # Quality report tracks coverage and reasonableness
        report.official_pe = official.pe_ttm
        report.calculated_pe = official.pe_ttm
        report.official_pb = official.pb
        report.calculated_pb = official.pb

        # Check data freshness
        today = pd.Timestamp.now().date()
        days_since = (today - observation_date).days
        if days_since > 7:
            report.issues.append(f"Data is {days_since} days old (stale)")

        # Check reasonableness
        if official.pe_ttm is not None:
            if official.pe_ttm > 100:
                report.issues.append(f"PE={official.pe_ttm:.1f} is extremely high")
                report.valid_weight = 0.5
            elif official.pe_ttm <= 0:
                report.issues.append(f"PE={official.pe_ttm:.1f} is non-positive")
                report.valid_weight = 0.3
            else:
                report.valid_weight = 1.0

        report.compute_severity()
        return report

    # ── AKShare API wrappers ──────────────────────────────────────

    def _fetch_pe_series(self, index_id: str, ak_name: str, start: date, end: date) -> pd.Series:
        try:
            import akshare as ak  # type: ignore

            df = ak.stock_index_pe_lg(symbol=ak_name)
            if df is None or df.empty:
                return pd.Series(dtype=float)

            df = df.copy()
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期").sort_index()

            pe_col = None
            for col in ["滚动市盈率", "静态市盈率"]:
                if col in df.columns:
                    pe_col = col
                    break
            if pe_col is None:
                return pd.Series(dtype=float)

            result = pd.to_numeric(df[pe_col], errors="coerce")
            s = pd.Timestamp(start)
            e = pd.Timestamp(end)
            return result.loc[s:e].dropna()  # type: ignore[index]
        except Exception:
            return pd.Series(dtype=float)

    def _fetch_pb_series(self, index_id: str, ak_name: str, start: date, end: date) -> pd.Series:
        try:
            import akshare as ak  # type: ignore

            df = ak.stock_index_pb_lg(symbol=ak_name)
            if df is None or df.empty:
                return pd.Series(dtype=float)

            df = df.copy()
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期").sort_index()

            pb_col = "市净率"
            if pb_col not in df.columns:
                return pd.Series(dtype=float)

            result = pd.to_numeric(df[pb_col], errors="coerce")
            s = pd.Timestamp(start)
            e = pd.Timestamp(end)
            return result.loc[s:e].dropna()  # type: ignore[index]
        except Exception:
            return pd.Series(dtype=float)

    def _fetch_dividend_series(
        self, index_id: str, csindex_code: str, start: date, end: date
    ) -> pd.Series:
        try:
            import akshare as ak  # type: ignore

            df = ak.stock_zh_index_value_csindex(symbol=csindex_code)
            if df is None or df.empty:
                return pd.Series(dtype=float)

            df = df.copy()
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期").sort_index()

            div_col = None
            for col in ["股息率1", "股息率2"]:
                if col in df.columns:
                    div_col = col
                    break
            if div_col is None:
                return pd.Series(dtype=float)

            result = pd.to_numeric(df[div_col], errors="coerce") / 100.0
            return result.dropna()
        except Exception:
            return pd.Series(dtype=float)
