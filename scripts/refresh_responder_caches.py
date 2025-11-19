#!/usr/bin/env python3
"""Rebuild responder hand-matrix caches for DriveHUD (Ignition).

This script recomputes the flop / turn / river responder hand matrices
from the DriveHUD HandHistories table and writes the refreshed payloads
to:

    var/cache/flop_responder_hand_matrix_<stake>.json
    var/cache/turn_responder_hand_matrix_<stake>.json
    var/cache/river_responder_hand_matrix_<stake>.json

Use this after changing responder aggregation logic (e.g., adding the
\"Unknown\" bucket) so the Response Matrix pages pick up the new schema.
"""

from __future__ import annotations

import json

from poker_analytics.config import build_data_paths
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_response_matrix_builder import (
    collect_flop_bet_events,
    collect_turn_bet_events,
    collect_river_bet_events,
)
from poker_analytics.services.flop_responder_hand_matrix import _aggregate as aggregate_flop
from poker_analytics.services.turn_responder_hand_matrix import _aggregate as aggregate_turn
from poker_analytics.services.river_responder_hand_matrix import _aggregate as aggregate_river


def main() -> int:
    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    data_paths.ensure_cache_dir()

    # Flop responder cache
    flop_events = collect_flop_bet_events()
    flop_payload = aggregate_flop(flop_events)
    flop_path = data_paths.cache_dir / f"flop_responder_hand_matrix_{stake_policy.cache_token()}.json"
    flop_path.write_text(json.dumps(flop_payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {flop_path}")

    # Turn responder cache
    turn_events = collect_turn_bet_events()
    turn_payload = aggregate_turn(turn_events)
    turn_path = data_paths.cache_dir / f"turn_responder_hand_matrix_{stake_policy.cache_token()}.json"
    turn_path.write_text(json.dumps(turn_payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {turn_path}")

    # River responder cache
    river_events = collect_river_bet_events()
    river_payload = aggregate_river(river_events)
    river_path = data_paths.cache_dir / f"river_responder_hand_matrix_{stake_policy.cache_token()}.json"
    river_path.write_text(json.dumps(river_payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {river_path}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

