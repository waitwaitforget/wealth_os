"""Data Quality CLI entry point.

Usage:
    python -m wealth_os.cli.data_quality <data_dir> [--output report.txt]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from wealth_os.infrastructure.data.repository import ParquetRepository
from wealth_os.validation.data_checks import DataBundleValidator


def main() -> None:
    parser = argparse.ArgumentParser(description="Data quality report CLI")
    parser.add_argument("data_dir", type=str, help="Path to data directory")
    parser.add_argument("--output", "-o", type=str, default=None, help="Write report to file")
    parser.add_argument("--since", type=str, default=None, help="Start date (YYYY-MM-DD)")
    args = parser.parse_args()

    repo = ParquetRepository(args.data_dir)
    version = repo.get_latest_version()

    if version is None:
        print("No data versions found.")
        sys.exit(1)

    instruments = repo.load_instruments(version=version)
    if not instruments:
        print("No instruments found.")
        sys.exit(1)

    instrument_ids = [i.instrument_id for i in instruments]
    start = date.fromisoformat(args.since) if args.since else date(2000, 1, 1)
    end = date(2099, 12, 31)
    bundle = repo.load_bundle(instrument_ids, start=start, end=end, version=version)

    validator = DataBundleValidator()
    report = validator.validate(bundle)
    report.data_version = version
    report.generated_at = version.created_at
    report.report_id = version.version_id

    summary = report.summary()
    print(summary)

    if args.output:
        with open(args.output, "w") as f:
            f.write(summary)

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
