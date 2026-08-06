"""Decision CLI — generate and review strategy decisions.

Usage:
    python -m wealth_os.cli.decision review --logs logs.jsonl
"""

from __future__ import annotations

import argparse
import sys

from wealth_os.decision.logger import DecisionLogger


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision Engine CLI")
    sub = parser.add_subparsers(dest="command")

    review_parser = sub.add_parser("review", help="Review historical decisions")
    review_parser.add_argument("--logs", type=str, required=True, help="Path to JSONL log file")

    args = parser.parse_args()

    if args.command == "review":
        logger = DecisionLogger.from_jsonl(args.logs)
        stats = logger.review()

        if not stats:
            print("No decisions found.")
            sys.exit(1)

        print("=== Decision Review ===")
        print(f"  Total decisions:     {stats['total_decisions']}")
        print(f"  Total trades:        {stats['total_trades']}")
        print(f"  No-action %:         {stats['no_action_pct']:.1%}")
        print(f"  Avg est cost (bps):  {stats['avg_est_cost_bps']:.1f}")
        print(f"  Avg confidence:      {stats['avg_confidence']:.1%}")
        print(f"  Cost slippage (bps): {stats['cost_slippage_bps']:.1f}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
