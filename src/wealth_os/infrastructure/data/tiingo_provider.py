"""Tiingo EOD data provider for US equities, ETFs, and indices.

Tiingo API: https://api.tiingo.com/documentation/end-of-day

Covers 80,000+ US stocks, ETFs, and mutual funds.  Free tier
allows 500 unique tickers/month and 50 requests/hour.

API token read from TIINGO_API env variable or .env file.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd

from wealth_os.domain.data_models import CorporateAction, Market

TIIngo_TICKER_MAP: dict[str, str] = {
    "SP500": "SPY",
    "NASDAQ100": "QQQ",
    "GOLD": "GLD",
}


def _get_api_token() -> str:
    """Read Tiingo API token from environment or .env file."""
    token = os.environ.get("TIINGO_API", "")
    if token:
        return token

    try:
        from dotenv import load_dotenv

        load_dotenv()
        return os.environ.get("TIINGO_API", "")
    except ImportError:
        return ""


class TiingoProvider:
    """Tiingo EOD data provider.

    Fetches daily adjusted close prices for US equities and ETFs.
    All data cached locally as Parquet files.
    """

    BASE_URL = "https://api.tiingo.com/tiingo/daily"

    def __init__(
        self,
        cache_dir: str | Path = "data/raw",
        rate_limit_seconds: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit_seconds
        self.max_retries = max_retries
        self._api_token: str | None = None

    @property
    def api_token(self) -> str:
        if self._api_token is None:
            self._api_token = _get_api_token()
        return self._api_token

    @property
    def name(self) -> str:
        return "tiingo"

    @property
    def markets(self) -> list[Market]:
        return [Market.NYSE, Market.NASDAQ]

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
        if not self.api_token:
            import warnings

            warnings.warn(
                "TIINGO_API not set in environment or .env file.",
                stacklevel=2,
            )
            return None

        ticker = TIIngo_TICKER_MAP.get(symbol)
        if ticker is None:
            return None

        cache_key = self._cache_key(ticker, start, end)
        cache_path = self.cache_dir / f"tiingo_{cache_key}.parquet"
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        df = self._fetch_tiingo_with_retry(ticker, start, end)
        if df is None or df.empty:
            return None

        result = _normalize_tiingo(df, start, end)
        if result is not None:
            result.to_parquet(cache_path)
        return result

    def _fetch_tiingo_with_retry(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> pd.DataFrame | None:
        import requests  # type: ignore

        url = f"{self.BASE_URL}/{ticker}/prices"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_token}",
        }
        params = {
            "startDate": str(start),
            "endDate": str(end),
            "format": "json",
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return pd.DataFrame(data)
                    return None
                elif resp.status_code == 429:
                    wait = min(120, 2 ** (attempt + 3))
                    time.sleep(wait)
                elif resp.status_code == 401:
                    import warnings

                    warnings.warn(
                        "Tiingo API: Invalid or expired API token.",
                        stacklevel=2,
                    )
                    return None
                else:
                    time.sleep(2**attempt)
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)

        return None

    def fetch_dividends(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def fetch_splits(self, symbols: list[str], start: date, end: date) -> list[CorporateAction]:
        return []

    def _cache_key(self, symbol: str, start: date, end: date) -> str:
        raw = f"{symbol}_{start}_{end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _normalize_tiingo(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame | None:
    """Normalize Tiingo EOD response: date → adjusted close."""
    if df.empty or "date" not in df.columns:
        return None

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    close_col = "adjClose" if "adjClose" in df.columns else "close"
    if close_col not in df.columns:
        return None

    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df.set_index("date").sort_index()
    # Tiingo returns UTC timestamps — strip timezone for naive comparison
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    df = df[(df.index >= s) & (df.index <= e)]

    return df[["close"]] if not df.empty else None
