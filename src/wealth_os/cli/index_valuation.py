"""Index valuation CLI.

Usage:
    python -m wealth_os.cli.index_valuation snapshot CSI300 2024-06-30
    python -m wealth_os.cli.index_valuation history CSI300 --start 2024-01-01 --end 2024-06-30
    python -m wealth_os.cli.index_valuation validate CSI300 2024-06-30
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from wealth_os.domain.factor_adapter import snapshot_to_dict
from wealth_os.infrastructure.data.index_valuation_provider import (
    INDEX_DEFINITIONS,
    IndexValuationProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index valuation queries")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Get single-date valuation")
    snap.add_argument("index", type=str)
    snap.add_argument("date", type=str, help="YYYY-MM-DD")

    hist = sub.add_parser("history", help="Get valuation history")
    hist.add_argument("index", type=str)
    hist.add_argument("--start", type=str, default="2018-01-01")
    hist.add_argument("--end", type=str, default="2024-12-31")
    hist.add_argument(
        "--metric",
        type=str,
        default="pe_ttm",
        choices=["pe_ttm", "pb", "dividend_yield", "earnings_yield"],
    )

    validate = sub.add_parser("validate", help="Validate vs official")
    validate.add_argument("index", type=str)
    validate.add_argument("date", type=str, help="YYYY-MM-DD")

    args = parser.parse_args()

    if args.index not in INDEX_DEFINITIONS:
        print(f"Unknown index: {args.index}")
        print(f"Available: {list(INDEX_DEFINITIONS)}")
        sys.exit(1)

    provider = IndexValuationProvider()

    if args.command == "snapshot":
        d = date.fromisoformat(args.date)
        result = provider.fetch_snapshot(args.index, d)
        if result is None:
            print(f"No data for {args.index} on {d}")
            sys.exit(1)
        for k, v in snapshot_to_dict(result).items():
            print(f"  {k}: {v}")

    elif args.command == "history":
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
        snapshots = provider.fetch_snapshot_range(args.index, start, end)
        if not snapshots:
            print(f"No data for {args.index} in {start} → {end}")
            sys.exit(1)

        metric = args.metric
        for s in snapshots:
            val = getattr(s, metric, None)
            if val is not None:
                print(f"  {s.observation_date.date()}  {val:.4f}")

    elif args.command == "validate":
        d = date.fromisoformat(args.date)
        report = provider.fetch_quality_report(args.index, d)
        if report is None:
            print(f"Cannot validate {args.index} on {d}")
            sys.exit(1)
        print(report.summary())


if __name__ == "__main__":
    main()
