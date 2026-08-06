"""AKShare-based market data provider for A-shares and HK stocks.

Fetches daily OHLCV data via AKShare.  All data is cached locally
and never re-fetched for the same (symbol, start, end) range.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path

import pandas as pd

from wealth_os.domain.data_models import CorporateAction, Market

# AKShare Sina API symbols (stable, long history)
A_SHARE_SINA_MAP: dict[str, str] = {
    "000300": "sh000300",
    "000905": "sh000905",
    "000922": "sh000922",
}

# HK indices use Sina API (East Money API is unreliable)
HK_SINA_SYMBOL_MAP: dict[str, str] = {
    "HSI": "HSI",
    "HSCEI": "HSCEI",
    "HSTECH": "HSTECH",
}


class AKShareProvider:
    """A-share and HK stock data via AKShare.

    Uses Sina API for both A-share (stock_zh_index_daily) and
    HK (stock_hk_index_daily_sina) to avoid East Money API flakiness.
    Data is cached as Parquet files under ``cache_dir``.
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/raw",
        rate_limit_seconds: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit_seconds
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def markets(self) -> list[Market]:
        return [Market.SSE, Market.SZSE, Market.HKEX]

    def fetch_bars(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        frames: dict[str, pd.Series] = {}
        for sym in symbols:
            df = self._fetch_one(sym, start, end)
            if df is not None and not df.empty:
                frames[sym] = df["close"]
            time.sleep(self.rate_limit)

        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames).sort_index()

    def _fetch_one(self, symbol: str, start: date, end: date) -> pd.DataFrame | None:
        cache_key = self._cache_key(symbol, start, end)
        cache_path = self.cache_dir / f"{cache_key}.parquet"
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        try:
            import akshare as ak  # type: ignore
        except ImportError:
            import warnings

            warnings.warn(
                "akshare not installed. Run: uv sync --group research",
                stacklevel=2,
            )
            return None

        raw_df = self._fetch_raw_with_retry(symbol, ak)
        if raw_df is None:
            return None

        df = _normalize_index_data(raw_df, start, end)
        if df is not None:
            df.to_parquet(cache_path)
        return df

    def _fetch_raw_with_retry(self, symbol: str, ak) -> pd.DataFrame | None:
        """Fetch raw data with retries for network flakiness."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._fetch_raw(symbol, ak)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait = 2**attempt
                    time.sleep(wait)
        if last_error is not None:
            import warnings

            warnings.warn(
                f"AKShare: failed to fetch {symbol} after {self.max_retries} retries: {last_error}",
                stacklevel=2,
            )
        return None

    def _fetch_raw(self, symbol: str, ak) -> pd.DataFrame | None:
        if symbol in A_SHARE_SINA_MAP:
            return ak.stock_zh_index_daily(symbol=A_SHARE_SINA_MAP[symbol])
        if symbol in HK_SINA_SYMBOL_MAP:
            return ak.stock_hk_index_daily_sina(symbol=HK_SINA_SYMBOL_MAP[symbol])
        return None

    def fetch_dividends(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def fetch_splits(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def _cache_key(self, symbol: str, start: date, end: date) -> str:
        raw = f"{symbol}_{start}_{end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _normalize_index_data(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame | None:
    """Normalize AKShare index output to (date, close) DataFrame."""
    date_col = None
    for col in ["date", "日期", "trade_date", "datetime"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        return None

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    close_col = None
    for col in ["close", "收盘"]:
        if col in df.columns:
            close_col = col
            break
    if close_col is None:
        return None

    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df.set_index(date_col).sort_index()

    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    df = df[(df.index >= s) & (df.index <= e)]  # type: ignore[operator]

    return df[["close"]] if not df.empty else None
