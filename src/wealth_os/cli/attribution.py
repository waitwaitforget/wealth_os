"""Attribution report — decompose strategy returns vs benchmarks.

Usage:
    python -m wealth_os.cli.attribution --data-dir data
"""

from __future__ import annotations

import argparse
import sys

from wealth_os.analytics.extended_metrics import full_performance_report
from wealth_os.domain.models import BacktestResult


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy attribution report")
    parser.add_argument("--result-path", type=str, help="Path to saved BacktestResult (pickle)")
    args = parser.parse_args()

    if args.result_path:
        import pickle

        with open(args.result_path, "rb") as f:
            result = pickle.load(f)
    else:
        print("Provide --result-path to a saved BacktestResult")
        sys.exit(1)

    if not isinstance(result, BacktestResult):
        print("Invalid result file")
        sys.exit(1)

    report = full_performance_report(result, label="Strategy Performance")
    print(report)


if __name__ == "__main__":
    main()
