"""Valuation data provider via AKShare.

Fetches PE/PB/dividend yield for A-share indices and converts
to earnings_yield and dividend_yield for factor computation.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd

# Map Wealth OS symbol → AKShare index name for PE/PB API
VALUATION_INDEX_MAP: dict[str, str] = {
    "CSI300": "沪深300",
    "CSI500": "中证500",
    "DIVIDEND": "上证红利",
}

# Default dividend yield estimates (annual %) when CSIndex data unavailable
DEFAULT_DIVIDEND_YIELDS: dict[str, float] = {
    "CSI300": 2.5,
    "CSI500": 1.8,
    "DIVIDEND": 4.5,
    "HSI": 3.5,
    "SP500": 1.4,
}


class ValuationProvider:
    """Fetch valuation metrics (PE → earnings_yield, dividend yield).

    Uses AKShare stock_index_pe_lg for daily PE data and
    stock_zh_index_value_csindex for dividend yield estimates.
    Data is cached under ``cache_dir``.
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/cache",
        rate_limit_seconds: float = 0.5,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit_seconds

    def fetch_valuation_metrics(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        """Return {metric_name: DataFrame} for given symbols and date range.

        Returns at minimum:
        - earnings_yield: DataFrame with columns=symbols, index=timestamp
        - dividend_yield: DataFrame with columns=symbols, index=timestamp
        """
        earnings = pd.DataFrame()
        for sym in symbols:
            df = self._fetch_earnings_yield(sym, start, end)
            if df is not None and not df.empty:
                earnings[sym] = df
            time.sleep(self.rate_limit)

        dividends = pd.DataFrame()
        for sym in symbols:
            df = self._fetch_dividend_yield(sym, start, end)
            if df is not None and not df.empty:
                dividends[sym] = df
            time.sleep(self.rate_limit)

        return {
            "earnings_yield": earnings,
            "dividend_yield": dividends,
        }

    def _fetch_earnings_yield(
        self, symbol: str, start: date, end: date
    ) -> pd.Series | None:
        idx_name = VALUATION_INDEX_MAP.get(symbol)
        if idx_name is None:
            return None

        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return None

        try:
            df = ak.stock_index_pe_lg(symbol=idx_name)
        except Exception:
            return None

        if df is None or df.empty:
            return None

        # AKShare returns columns: 日期, 指数, ..., 滚动市盈率, ...
        pe_col = None
        for col in ["滚动市盈率", "静态市盈率"]:
            if col in df.columns:
                pe_col = col
                break
        if pe_col is None:
            return None

        df = df.copy()
        df["日期"] = pd.to_datetime(df["日期"])
        df["earnings_yield"] = 1.0 / pd.to_numeric(df[pe_col], errors="coerce")
        df = df.set_index("日期").sort_index()

        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        result = df.loc[s:e, "earnings_yield"]  # type: ignore[index]
        return result.dropna() if not result.empty else None

    def _fetch_dividend_yield(
        self, symbol: str, start: date, end: date
    ) -> pd.Series | None:
        # Try CSIndex for recent dividend yield
        csindex_code = {
            "CSI300": "000300",
            "CSI500": "000905",
            "DIVIDEND": "000922",
        }.get(symbol)

        if csindex_code:
            try:
                import akshare as ak  # type: ignore

                df = ak.stock_zh_index_value_csindex(symbol=csindex_code)
                if df is not None and not df.empty:
                    div_col = None
                    for col in ["股息率1", "股息率2"]:
                        if col in df.columns:
                            div_col = col
                            break
                    if div_col:
                        df = df.copy()
                        df["日期"] = pd.to_datetime(df["日期"])
                        recent_div = (
                            pd.to_numeric(df[div_col].iloc[0], errors="coerce") / 100.0
                        )
                        if pd.notna(recent_div) and recent_div > 0:
                            return pd.Series(
                                recent_div,
                                index=pd.date_range(start, end, freq="D"),
                                name=symbol,
                            )
            except Exception:
                pass

        # Fallback to constant estimate
        default = DEFAULT_DIVIDEND_YIELDS.get(symbol)
        if default is not None:
            return pd.Series(
                default / 100.0,
                index=pd.date_range(start, end, freq="D"),
                name=symbol,
            )
        return None
