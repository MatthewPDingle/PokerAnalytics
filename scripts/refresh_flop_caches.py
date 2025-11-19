#!/usr/bin/env python3
"""Utility to clear cached flop/turn/river analytics payloads and rebuild response matrices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(SRC_ROOT), str(REPO_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from poker_analytics.config import build_data_paths
from poker_analytics.services.cache_refresh import (
    CACHE_PATTERNS,
    TURN_CACHE_PATTERNS,
    RIVER_CACHE_PATTERNS,
    refresh_flop_caches,
    refresh_turn_caches,
    refresh_river_caches,
)
from poker_analytics.services.flop_hand_matrix import load_flop_hand_matrix
from poker_analytics.services.flop_responder_hand_matrix import load_flop_responder_hand_matrix


def _remove_matching(cache_dir: Path, patterns: Iterable[str]) -> list[Path]:
    removed: list[Path] = []
    for pattern in patterns:
        for path in cache_dir.glob(pattern):
            try:
                path.unlink()
            except OSError:
                continue
            removed.append(path)
    return removed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-hands",
        type=int,
        default=None,
        help="Optional limit for rebuilding caches (useful for smoke tests).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Delete caches without rebuilding the response matrices.",
    )
    return parser.parse_args(argv or sys.argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    data_paths = build_data_paths()
    cache_dir = data_paths.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_build:
        combined_patterns = tuple(dict.fromkeys((*CACHE_PATTERNS, *TURN_CACHE_PATTERNS, *RIVER_CACHE_PATTERNS)))
        removed = _remove_matching(cache_dir, combined_patterns)
        if removed:
            print("Removed cache files:")
            for path in sorted(removed):
                print(f"  - {path}")
        else:
            print("No cache files matched; nothing was removed.")
        print("Skipped rebuilding response matrices (--skip-build).")
    else:
        flop_destination = refresh_flop_caches(max_hands=args.max_hands, rebuild=True)
        print(f"Flop caches cleared and response matrix rebuilt: {flop_destination}")

        # Warm flop hand-matrix caches so the Flop Response Matrix page
        # does not have to build them on first load.
        try:
            _ = load_flop_hand_matrix()
            _ = load_flop_responder_hand_matrix()
            print("Flop hand matrices (bettor + responder) cache ensured.")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Warning: unable to warm flop hand matrices: {exc}")

        # NOTE: Turn/river cache rebuilds are temporarily disabled while the
        # turn/river event builders are being refactored for hero-exclusion
        # semantics. Existing turn/river caches remain valid; when needed,
        # introduce dedicated refresh scripts or re-enable the calls below:
        # turn_destination = refresh_turn_caches(max_hands=args.max_hands, rebuild=True)
        # river_destination = refresh_river_caches(max_hands=args.max_hands, rebuild=True)
        # print(f"Turn caches cleared and response matrix rebuilt: {turn_destination}")
        # print(f"River caches cleared and response matrix rebuilt: {river_destination}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
