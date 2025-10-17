#!/usr/bin/env python3
"""Materialise flop response matrix aggregates into the cache directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from poker_analytics.services.flop_response_matrix_builder import write_flop_response_cache


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-hands",
        type=int,
        default=None,
        help="Optional limit on the number of hero hands to process (for smoke tests)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Explicit output path for the cache file (defaults to var/cache/flop_response_matrix.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    destination = write_flop_response_cache(output_path=args.output, max_hands=args.max_hands)
    print(f"Flop response matrix written to {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

