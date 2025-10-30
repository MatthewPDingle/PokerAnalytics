"""Aggregations for multi-street betting lines."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA, BUCKET_KEYS
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_response_matrix_builder import collect_line_events

LINE_PREFIX_LABELS: Mapping[str, str] = {
    "xc": "Flop Check-Call",
    "c": "Flop Call",
    "xr": "Flop Check-Raise",
    "r": "Flop Raise",
}

LINE_SUFFIX_LABELS: Mapping[str, str] = {
    "b": "Turn Bet",
    "x": "Turn Check",
    "c": "Turn Call",
    "f": "Turn Fold",
}

LINE_PREFIX_ORDER: Sequence[str] = tuple(LINE_PREFIX_LABELS.keys())
LINE_SUFFIX_ORDER: Sequence[str] = tuple(LINE_SUFFIX_LABELS.keys())

RESPONSE_TYPE_LABELS: Mapping[str, str] = {
    "call": "Call",
    "raise": "Raise",
}

BET_TYPE_ORDER: Sequence[str] = ("cbet", "donk", "stab")
POSITION_ORDER: Sequence[str] = ("IP", "OOP")


def load_line_explorer() -> dict:
    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"line_explorer_{stake_policy.cache_token()}.json"

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("version") == CURRENT_VERSION:
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    data_paths.ensure_cache_dir()

    events = collect_line_events()

    payload = build_line_explorer_payload(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_line_explorer_payload(events: Sequence[Mapping[str, object]]) -> dict:
    aggregate: MutableMapping[
        Tuple[str, str, str, str, int, str],
        MutableMapping[str, Dict[str, float]],
    ] = defaultdict(
        lambda: {
            key: {
                "events": 0.0,
                "fold_events": 0.0,
                "call_events": 0.0,
                "raise_events": 0.0,
                "ratio_sum": 0.0,
                "bet_sum_bb": 0.0,
            }
            for key in BUCKET_KEYS
        }
    )

    line_keys: set[str] = set()
    hero_positions: set[str] = set()
    bet_types: set[str] = set()
    positions: set[str] = set()
    player_counts: set[int] = set()
    response_types: set[str] = set()

    for event in events:
        line_key = str(event.get("line_key") or "")
        hero_position = str(event.get("hero_position") or "UNKNOWN")
        bet_type = str(event.get("bet_type") or "")
        position = str(event.get("position") or "")
        response_type = str(event.get("response_type") or "")
        player_count_raw = event.get("player_count")
        bucket_key = event.get("turn_bucket_key")
        ratio_value_raw = event.get("turn_ratio")
        bet_amount_bb_raw = event.get("bet_amount_bb")
        outcome = str(event.get("outcome") or "fold")

        if bucket_key not in BUCKET_KEYS:
            continue

        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            continue

        try:
            ratio_value = float(ratio_value_raw)
        except (TypeError, ValueError):
            ratio_value = 0.0

        try:
            bet_amount_bb = float(bet_amount_bb_raw)
        except (TypeError, ValueError):
            bet_amount_bb = 0.0

        scenario_key = (line_key, hero_position, bet_type, position, player_count, response_type)
        bucket_map = aggregate[scenario_key]
        bucket_metrics = bucket_map[bucket_key]

        bucket_metrics["events"] += 1
        if outcome == "raise":
            bucket_metrics["raise_events"] += 1
        elif outcome == "call":
            bucket_metrics["call_events"] += 1
        else:
            bucket_metrics["fold_events"] += 1
        bucket_metrics["ratio_sum"] += ratio_value
        bucket_metrics["bet_sum_bb"] += bet_amount_bb

        line_keys.add(line_key)
        hero_positions.add(hero_position)
        if bet_type:
            bet_types.add(bet_type)
        if position:
            positions.add(position)
        player_counts.add(player_count)
        if response_type:
            response_types.add(response_type)

    scenarios: List[dict] = []
    for (line_key, hero_position, bet_type, position, player_count, response_type), bucket_map in sorted(
        aggregate.items(),
        key=lambda item: (
            _line_rank(item[0][0]),
            _hero_position_rank(item[0][1]),
            _bet_type_rank(item[0][2]),
            _position_rank(item[0][3]),
            item[0][4],
            _response_type_rank(item[0][5]),
        ),
    ):
        scenarios.append(
            {
                "line_key": line_key,
                "hero_position": hero_position,
                "bet_type": bet_type,
                "position": position,
                "player_count": player_count,
                "response_type": response_type,
                "metrics": [
                    {
                        "bucket_key": meta.key,
                        "bucket_label": meta.label,
                        "events": int(bucket_map[meta.key]["events"]),
                        "fold_events": int(bucket_map[meta.key]["fold_events"]),
                        "call_events": int(bucket_map[meta.key]["call_events"]),
                        "raise_events": int(bucket_map[meta.key]["raise_events"]),
                        "avg_ratio": (
                            bucket_map[meta.key]["ratio_sum"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                        "avg_bet_bb": (
                            bucket_map[meta.key]["bet_sum_bb"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                    }
                    for meta in BUCKET_METADATA
                ],
            }
        )

    return {
        "version": CURRENT_VERSION,
        "line_definitions": [
            {"key": key, "label": _format_line_label(key)}
            for key in sorted(line_keys, key=_line_rank)
        ],
        "bucket_order": [meta.__dict__ for meta in BUCKET_METADATA],
        "bet_types": [
            {"key": key, "label": key.title()}
            for key in sorted(bet_types, key=_bet_type_rank)
        ],
        "positions": [
            {"key": key, "label": key if key in POSITION_ORDER else key.title()}
            for key in sorted(positions, key=_position_rank)
        ],
        "hero_positions": sorted(hero_positions, key=_hero_position_rank),
        "player_counts": sorted(player_counts),
        "response_types": [
            {"key": key, "label": RESPONSE_TYPE_LABELS.get(key, key.title())}
            for key in sorted(response_types, key=_response_type_rank)
        ],
        "scenarios": scenarios,
    }


def _split_line_key(key: str) -> tuple[str, str]:
    if "_turn_" in key:
        prefix, suffix = key.split("_turn_", 1)
        return prefix, suffix
    return key, ""


def _format_line_label(key: str) -> str:
    prefix, suffix = _split_line_key(key)
    prefix_label = LINE_PREFIX_LABELS.get(prefix, prefix.upper())
    suffix_label = LINE_SUFFIX_LABELS.get(suffix, suffix.upper())
    if suffix_label:
        return f"{prefix_label} → {suffix_label}"
    return prefix_label


def _line_rank(key: str) -> tuple[int, int]:
    prefix, suffix = _split_line_key(key)
    try:
        prefix_idx = LINE_PREFIX_ORDER.index(prefix)
    except ValueError:
        prefix_idx = len(LINE_PREFIX_ORDER)
    try:
        suffix_idx = LINE_SUFFIX_ORDER.index(suffix)
    except ValueError:
        suffix_idx = len(LINE_SUFFIX_ORDER)
    return (prefix_idx, suffix_idx)


def _bet_type_rank(value: str) -> int:
    try:
        return BET_TYPE_ORDER.index(value)
    except ValueError:
        return len(BET_TYPE_ORDER)


def _position_rank(value: str) -> int:
    try:
        return POSITION_ORDER.index(value)
    except ValueError:
        return len(POSITION_ORDER)


def _hero_position_rank(value: str) -> int:
    ordering = [
        "SB",
        "BB",
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
        "BTN",
        "UNKNOWN",
    ]
    try:
        return ordering.index(value)
    except ValueError:
        return len(ordering)


def _response_type_rank(value: str) -> int:
    try:
        return ["call", "raise"].index(value)
    except ValueError:
        return 2


__all__ = ["load_line_explorer", "build_line_explorer_payload"]
CURRENT_VERSION = 2
