#!/usr/bin/env python3
"""Build PokerStars NL10 turn hand matrix cache from raw HH text files.

This script parses PokerStars NL10 hand histories under a given root
directory (default: ``data/NL10``), extracts turn bet events where the
bettor's hole cards are revealed at showdown, and aggregates them using
the existing ``turn_hand_matrix`` aggregator.

The resulting payload is written to:

    var/cache/pokerstars_nl10/turn_hand_matrix_<stake_token>.json

where ``<stake_token>`` is derived from ``StakePolicy.from_environment()``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from poker_analytics.config import build_data_paths
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.importers.pokerstars_text import collect_pokerstars_turn_events
from poker_analytics.services.turn_hand_matrix import _aggregate as aggregate_turn_hands, CURRENT_VERSION


def parse_args(argv: list[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "--root",
      type=Path,
      default=Path("data/NL10"),
      help="Root directory containing PokerStars NL10 HH text files.",
  )
  return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
  args = parse_args(argv or sys.argv[1:])

  root = args.root
  if not root.exists() or not root.is_dir():
      raise SystemExit(f"Root directory not found or not a directory: {root}")

  stake_policy = StakePolicy.from_environment()

  events = collect_pokerstars_turn_events(root, stake_policy=stake_policy)
  if not events:
      print("No eligible PokerStars turn events found; nothing to write.")
      return 0

  payload = aggregate_turn_hands(events)
  # Ensure version marker is present and matches the current schema.
  payload["version"] = CURRENT_VERSION

  data_paths = build_data_paths()
  cache_dir = data_paths.cache_dir / "pokerstars_nl10"
  cache_dir.mkdir(parents=True, exist_ok=True)
  filename = f"turn_hand_matrix_{stake_policy.cache_token()}.json"
  destination = cache_dir / filename
  destination.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
  print(f"PokerStars turn hand matrix written to {destination}")
  return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
  raise SystemExit(main())

