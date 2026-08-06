"""Data ingestion CLI.

Usage:
    python -m wealth_os.cli.ingest --symbols CSI300,HSI --start 2020-01-01 --end 2024-12-31
    python -m wealth_os.cli.ingest --all --data-dir data
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest market data into Wealth OS")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols")
    parser.add_argument("--all", action="store_true", help="Ingest all known symbols")
    parser.add_argument("--start", type=str, default="2018-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, skip persist")
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

    print(f"Ingesting {len(valid)} symbols: {valid}")
    print(f"Range: {start} → {end}")
    print(f"Data dir: {args.data_dir}")
    print()

    # Step 1: Fetch
    provider = AKShareProvider(cache_dir=f"{args.data_dir}/raw")
    akshare_symbols = [SYMBOL_TO_AKSHARE.get(s, s) for s in valid]
    prices = provider.fetch_bars(akshare_symbols, start, end)

    fetched = list(prices.columns) if not prices.empty else []
    akshare_to_ws = {v: k for k, v in SYMBOL_TO_AKSHARE.items()}

    # Rename columns from AKShare symbol to Wealth OS symbol
    rename_map = {}
    for col in prices.columns:
        rename_map[col] = akshare_to_ws.get(col, col)
    prices = prices.rename(columns=rename_map)
    fetched = [rename_map.get(c, c) for c in fetched]

    missing = [s for s in valid if s not in fetched]

    print(f"Fetched: {len(fetched)}/{len(valid)}")
    for sym in fetched:
        ws_sym = akshare_to_ws.get(sym, sym)
        s = prices[sym].dropna()
        print(f"  {ws_sym}: {len(s)} rows, {s.index[0].date()} → {s.index[-1].date()}")
    if missing:
        print(f"Missing: {missing}")

    if prices.empty:
        print("No data fetched.")
        sys.exit(1)

    # Step 2: Validate
    from wealth_os.domain.data_models import MarketDataBundle

    bundle = MarketDataBundle(prices=prices)
    validator = DataBundleValidator()
    report = validator.validate(bundle)
    print(f"\n{report.summary()}")

    if report.error_count > 0:
        print("Data quality errors found — aborting ingest.")
        sys.exit(1)

    # Step 3: Save
    repo = ParquetRepository(root_dir=args.data_dir)

    instruments = []
    for sym in fetched:
        ws_sym = akshare_to_ws.get(sym, sym)
        inst_id, name, ac, mkt = UNIVERSE[ws_sym]
        instruments.append(
            InstrumentMaster(
                instrument_id=inst_id,
                symbol=sym,
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
