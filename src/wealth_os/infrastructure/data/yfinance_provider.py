"""Yahoo Finance market data provider.

Fetches daily OHLCV data for US equities, ETFs, BTC, gold, and
global indices via Yahoo Finance.  All data is cached locally.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path

import pandas as pd

from wealth_os.domain.data_models import CorporateAction, Market

# Wealth OS symbol → Yahoo Finance ticker
YFINANCE_TICKER_MAP: dict[str, str] = {
    "SP500": "^GSPC",
    "NASDAQ100": "^NDX",
    "GOLD": "GC=F",
    "BTC": "BTC-USD",
    "BOND": "AGG",
}

# PE data available via yfinance for these tickers
YFINANCE_VALUATION_MAP: dict[str, str] = {
    "SP500": "^GSPC",
    "NASDAQ100": "^NDX",
}


class YahooFinanceProvider:
    """Market data via Yahoo Finance for US/BTC/global assets.

    Handles rate limiting with exponential backoff.  All fetched
    data is cached as Parquet files under ``cache_dir``.
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/raw",
        rate_limit_seconds: float = 2.0,
        max_retries: int = 5,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit_seconds
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def markets(self) -> list[Market]:
        return [Market.NYSE, Market.NASDAQ, Market.CRYPTO, Market.FX]

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
        ticker = YFINANCE_TICKER_MAP.get(symbol)
        if ticker is None:
            return None

        cache_key = self._cache_key(symbol, start, end)
        cache_path = self.cache_dir / f"yf_{cache_key}.parquet"
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            import warnings

            warnings.warn(
                "yfinance not installed. Run: uv sync --group research",
                stacklevel=2,
            )
            return None

        df = self._download_with_retry(yf, ticker, start, end)
        if df is None or df.empty:
            return None

        df = _normalize_yfinance(df, start, end)
        if df is not None:
            df.to_parquet(cache_path)
        return df

    def _download_with_retry(
        self,
        yf,
        ticker: str,
        start: date,
        end: date,
    ) -> pd.DataFrame | None:
        for attempt in range(self.max_retries):
            try:
                df = yf.download(
                    ticker,
                    start=str(start),
                    end=str(end),
                    progress=False,
                    auto_adjust=True,
                )
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df
            except Exception as exc:
                if "Rate limited" in str(exc) or "429" in str(exc):
                    wait = min(120, 2 ** (attempt + 3))  # 8, 16, 32, 64, 120s
                    time.sleep(wait)
                elif attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    import warnings

                    warnings.warn(
                        f"Yahoo Finance: failed to fetch {ticker}: {exc}",
                        stacklevel=2,
                    )
        return None

    def fetch_dividends(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def fetch_splits(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def _cache_key(self, symbol: str, start: date, end: date) -> str:
        raw = f"{symbol}_{start}_{end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _normalize_yfinance(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame | None:
    """Normalize yfinance multilevel columns to (timestamp, close)."""
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        close_col = None
        for col in df.columns:
            if col[0] == "Close":
                close_col = col
                break
        if close_col is not None:
            close_series = df[close_col]
            result = close_series.to_frame(name="close")
        else:
            return None
    elif "Close" in df.columns:
        result = df[["Close"]].rename(columns={"Close": "close"})
    else:
        return None

    result.index = pd.DatetimeIndex(result.index)
    result.index.name = "date"
    result = result.sort_index()

    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    result = result[(result.index >= s) & (result.index <= e)]

    return result if not result.empty else None
