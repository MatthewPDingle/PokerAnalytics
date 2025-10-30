"""Responder hand distributions for line explorer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.flop_hand_categories import (
    DRAW_CATEGORIES,
    GROUP_DEFINITIONS,
    PRIMARY_HAND_TYPES,
)
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA
from poker_analytics.services.flop_response_matrix_builder import collect_line_events

HAND_TYPE_ORDER: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES)
HAND_TYPE_SET = set(HAND_TYPE_ORDER)

BET_TYPE_ORDER: Sequence[str] = ("cbet", "donk", "stab")
POSITION_ORDER: Sequence[str] = ("IP", "OOP")
RESPONSE_TYPE_ORDER: Sequence[str] = ("call", "raise")

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


def load_line_responder_hand_matrix() -> dict:
    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"line_responder_hand_matrix_{stake_policy.cache_token()}.json"

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

    payload = build_line_responder_hand_payload(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_line_responder_hand_payload(events: Iterable[Mapping[str, object]]) -> dict:
    scenario_map: MutableMapping[
        Tuple[str, str, str, str, int, str],
        MutableMapping[str, Dict[str, object]],
    ] = {}

    hero_positions: set[str] = set()
    bet_types: set[str] = set()
    positions: set[str] = set()
    player_counts: set[int] = set()
    response_types: set[str] = set()
    line_keys: set[str] = set()

    for event in events:
        line_key = str(event.get("line_key") or "")
        response_type = str(event.get("response_type") or "")
        hero_position = str(event.get("hero_position") or "UNKNOWN")
        bet_type = str(event.get("bet_type") or "")
        position = str(event.get("position") or "")
        player_count_raw = event.get("player_count")
        bucket_key = event.get("turn_bucket_key")
        hand_primary = str(event.get("hand_primary") or "")
        has_flush_draw = bool(event.get("has_flush_draw"))
        has_oesd_dg = bool(event.get("has_oesd_dg"))

        if bucket_key not in HAND_TYPE_BUCKET_KEYS:
            continue
        if hand_primary not in HAND_TYPE_SET:
            continue

        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            continue

        scenario_key = (line_key, hero_position, bet_type, position, player_count, response_type)
        bucket_map = scenario_map.setdefault(scenario_key, _initial_bucket_map())
        bucket_stats = bucket_map[bucket_key]
        bucket_stats["events"] += 1
        bucket_stats["categories"][hand_primary] += 1
        if has_flush_draw:
            bucket_stats["categories"]["Flush Draw"] += 1
        if has_oesd_dg:
            bucket_stats["categories"]["OESD/DG"] += 1

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
        scenario_map.items(),
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
                        "bucket_key": bucket_key,
                        "bucket_label": label,
                        "events": stats["events"],
                        "categories": dict(stats["categories"]),
                    }
                    for bucket_key, label, stats in _iter_bucket_stats(bucket_map)
                ],
            }
        )

    return {
        "version": CURRENT_VERSION,
        "bucket_order": [{"key": key, "label": label} for key, label in HAND_TYPE_BUCKETS],
        "hand_types": [
            {"key": label, "label": label, "kind": "primary"}
            for label in PRIMARY_HAND_TYPES
        ]
        + [
            {"key": label, "label": label, "kind": "draw"}
            for label in DRAW_CATEGORIES
        ],
        "groupings": [
            {
                "key": "grouped",
                "label": "Grouped View",
                "groups": [
                    {"key": label, "label": label, "members": list(members)}
                    for label, members in GROUP_DEFINITIONS
                ],
            }
        ],
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
            {"key": key, "label": key.title()}
            for key in sorted(response_types, key=_response_type_rank)
        ],
        "line_definitions": [
            {"key": key, "label": _format_line_label(key)}
            for key in sorted(line_keys, key=_line_rank)
        ],
        "scenarios": scenarios,
    }


HAND_TYPE_BUCKETS = [(meta.key, meta.label) for meta in BUCKET_METADATA]
HAND_TYPE_BUCKET_KEYS = {meta.key for meta in BUCKET_METADATA}


def _initial_bucket_map() -> Dict[str, Dict[str, object]]:
    return {
        key: {
            "events": 0,
            "categories": {label: 0 for label in HAND_TYPE_ORDER},
        }
        for key in HAND_TYPE_BUCKET_KEYS
    }


def _iter_bucket_stats(bucket_map: Mapping[str, Dict[str, object]]):
    for key, label in HAND_TYPE_BUCKETS:
        stats = bucket_map.get(key, {"events": 0, "categories": {label: 0 for label in HAND_TYPE_ORDER}})
        yield key, label, stats


def _split_line_key(value: str) -> tuple[str, str]:
    if "_turn_" in value:
        prefix, suffix = value.split("_turn_", 1)
        return prefix, suffix
    return value, ""


def _format_line_label(value: str) -> str:
    prefix, suffix = _split_line_key(value)
    prefix_label = LINE_PREFIX_LABELS.get(prefix, prefix.upper())
    suffix_label = LINE_SUFFIX_LABELS.get(suffix, suffix.upper())
    if suffix_label:
        return f"{prefix_label} → {suffix_label}"
    return prefix_label


def _line_rank(value: str) -> tuple[int, int]:
    prefix, suffix = _split_line_key(value)
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
        return RESPONSE_TYPE_ORDER.index(value)
    except ValueError:
        return len(RESPONSE_TYPE_ORDER)


__all__ = [
    "load_line_responder_hand_matrix",
    "build_line_responder_hand_payload",
]
CURRENT_VERSION = 2
