#!/usr/bin/env python3
"""Utility to clear cached flop analytics payloads and rebuild the response matrix."""

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
from poker_analytics.services.cache_refresh import CACHE_PATTERNS, refresh_flop_caches


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
        help="Delete caches without rebuilding the flop response matrix.",
    )
    return parser.parse_args(argv or sys.argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    data_paths = build_data_paths()
    cache_dir = data_paths.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_build:
        removed = _remove_matching(cache_dir, CACHE_PATTERNS)
        if removed:
            print("Removed cache files:")
            for path in sorted(removed):
                print(f"  - {path}")
        else:
            print("No cache files matched; nothing was removed.")
        print("Skipped rebuilding flop response matrix (--skip-build).")
    else:
        destination = refresh_flop_caches(max_hands=args.max_hands, rebuild=True)
        print(f"Flop caches cleared and response matrix rebuilt: {destination}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
