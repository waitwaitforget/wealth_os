"""Data ingestion CLI.

Usage:
    python -m wealth_os.cli.ingest --symbols CSI300,SP500 --start 2020-01-01
    python -m wealth_os.cli.ingest --all --data-dir data
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from wealth_os.domain.data_models import (
    AssetClass,
    InstrumentMaster,
    Market,
)
from wealth_os.infrastructure.data.providers import AKShareProvider
from wealth_os.infrastructure.data.repository import ParquetRepository
from wealth_os.validation.data_checks import DataBundleValidator

UNIVERSE: dict[str, tuple[str, str, str, str]] = {
    "CSI300": ("CSI300", "沪深300", "equity_index", "SSE"),
    "CSI500": ("CSI500", "中证500", "equity_index", "SSE"),
    "DIVIDEND": ("DIVIDEND", "中证红利", "equity_index", "SSE"),
    "HSI": ("HSI", "恒生指数", "equity_index", "HKEX"),
    "HSCEI": ("HSCEI", "恒生国企", "equity_index", "HKEX"),
    "HSTECH": ("HSTECH", "恒生科技", "equity_index", "HKEX"),
    "SP500": ("SP500", "标普500", "equity_index", "NYSE"),
    "NASDAQ100": ("NASDAQ100", "纳斯达克100", "equity_index", "NASDAQ"),
    "GOLD": ("GOLD", "黄金", "gold", "FX"),
    "BTC": ("BTC", "比特币", "digital_asset", "CRYPTO"),
}

SYMBOL_TO_AKSHARE: dict[str, str] = {
    "CSI300": "000300",
    "CSI500": "000905",
    "DIVIDEND": "000922",
    "HSI": "HSI",
    "HSCEI": "HSCEI",
    "HSTECH": "HSTECH",
}

YFINANCE_SYMBOLS = {"SP500", "NASDAQ100", "GOLD", "BTC"}


def _fetch_akshare(symbols: list[str], start: date, end: date, data_dir: str) -> pd.DataFrame:
    provider = AKShareProvider(cache_dir=f"{data_dir}/raw")
    mapped = [SYMBOL_TO_AKSHARE.get(s, s) for s in symbols]
    prices = provider.fetch_bars(mapped, start, end)

    rename = {v: k for k, v in SYMBOL_TO_AKSHARE.items()}
    return prices.rename(columns=lambda c: rename.get(c, c))


def _fetch_yfinance(symbols: list[str], start: date, end: date, data_dir: str) -> pd.DataFrame:
    try:
        from wealth_os.infrastructure.data.yfinance_provider import YahooFinanceProvider

        provider = YahooFinanceProvider(cache_dir=f"{data_dir}/raw")
        return provider.fetch_bars(symbols, start, end)
    except Exception:
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest market data into Wealth OS")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols")
    parser.add_argument("--all", action="store_true", help="Ingest all known symbols")
    parser.add_argument("--start", type=str, default="2018-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument(
        "--skip-yfinance", action="store_true", help="Skip Yahoo Finance (slow/ratelimited)"
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    if args.all:
        symbols = list(UNIVERSE)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        print("Specify --symbols or --all")
        sys.exit(1)

    valid = [s for s in symbols if s in UNIVERSE]
    invalid = [s for s in symbols if s not in UNIVERSE]
    if invalid:
        print(f"Skipping unknown symbols: {invalid}")
    if not valid:
        print("No valid symbols to ingest.")
        sys.exit(1)

    akshare_symbols = [s for s in valid if s not in YFINANCE_SYMBOLS]
    yf_symbols = [s for s in valid if s in YFINANCE_SYMBOLS]
    if args.skip_yfinance:
        yf_symbols = []

    print(f"Ingesting {len(valid)} symbols: {valid}")
    print(f"  AKShare: {akshare_symbols}")
    print(f"  Yahoo Finance: {yf_symbols}")
    print(f"  Range: {start} → {end}")
    print()

    # Step 1: Fetch from both providers
    frames = []

    if akshare_symbols:
        prices_a = _fetch_akshare(akshare_symbols, start, end, args.data_dir)
        if not prices_a.empty:
            frames.append(prices_a)
            for s in akshare_symbols:
                if s in prices_a.columns:
                    col = prices_a[s].dropna()
                    n = len(col)
                    if n:
                        print(
                            f"  [AKShare] {s}: {n} rows, "
                            f"{col.index[0].date()} → {col.index[-1].date()}"
                        )
                else:
                    print(f"  [AKShare] {s}: MISSING")
        else:
            for s in akshare_symbols:
                print(f"  [AKShare] {s}: FAILED")

    if yf_symbols:
        prices_y = _fetch_yfinance(yf_symbols, start, end, args.data_dir)
        if not prices_y.empty:
            frames.append(prices_y)
            for s in yf_symbols:
                if s in prices_y.columns:
                    col = prices_y[s].dropna()
                    n = len(col)
                    if n:
                        print(
                            f"  [YFinance] {s}: {n} rows, "
                            f"{col.index[0].date()} → {col.index[-1].date()}"
                        )
                else:
                    print(f"  [YFinance] {s}: MISSING (ratelimited)")
        else:
            for s in yf_symbols:
                print(f"  [YFinance] {s}: FAILED (ratelimited)")

    if not frames:
        print("No data fetched.")
        sys.exit(1)

    prices = pd.concat(frames, axis=1).sort_index()

    # Step 2: Validate
    from wealth_os.domain.data_models import MarketDataBundle

    bundle = MarketDataBundle(prices=prices)
    validator = DataBundleValidator()
    report = validator.validate(bundle)
    print(f"\n{report.summary()}")

    if report.error_count > 0:
        print("Data quality errors found - aborting ingest.")
        sys.exit(1)

    # Step 3: Save
    repo = ParquetRepository(root_dir=args.data_dir)

    instruments = []
    for col in prices.columns:
        inst_id, name, ac, mkt = UNIVERSE[col]
        instruments.append(
            InstrumentMaster(
                instrument_id=inst_id,
                symbol=col,
                name=name,
                asset_class=AssetClass(ac),
                market=Market(mkt),
                currency="CNY" if mkt in ("SSE", "SZSE") else "USD",
            )
        )

    version = repo.create_version(instruments=instruments, bars=prices)
    print(f"\nSaved version: {version.version_id}")
    print(f"Instruments: {len(instruments)}")
    print(f"Data range: {prices.index[0].date()} → {prices.index[-1].date()}")
    print("\nDone.")


if __name__ == "__main__":
    main()
