#!/usr/bin/env python3
"""Materialise preflop response-curve aggregates into the cache directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from poker_analytics.services.preflop_response_curves_builder import write_response_curve_cache


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-hands",
        type=int,
        default=None,
        help="Optional cap on the number of hands to scan (useful for smoke tests)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Explicit path for the cache file (defaults to var/cache/preflop_response_curves.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = write_response_curve_cache(output_path=args.output, max_hands=args.max_hands)
    print(f"Response-curve cache written to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    raise SystemExit(main())

