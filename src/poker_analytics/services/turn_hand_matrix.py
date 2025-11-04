"""Aggregations for hero turn hand categories across bet-size buckets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.flop_hand_categories import (
    DRAW_CATEGORIES,
    GROUP_DEFINITIONS,
    PRIMARY_HAND_TYPES,
)
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.data.textures import TURN_TEXTURE_SPECS, turn_texture_keys
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA, BUCKET_KEYS, bucket_keys_for_event
from poker_analytics.services.flop_preflop_utils import (
    PREFLOP_ANY_KEY,
    PREFLOP_OPTIONS,
    PREFLOP_ORDER,
    preflop_bucket,
    preflop_keys,
)
from poker_analytics.services.flop_response_matrix_builder import collect_turn_bet_events

HAND_TYPE_ORDER: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES)
HAND_TYPE_SET = set(HAND_TYPE_ORDER)

BET_LINE_LABELS: Mapping[str, str] = {
    "double_barrel": "Double Barrel (B;B)",
    "delayed_cbet": "Delayed C-Bet (X;B)",
    "probe": "Probe (X-X;B)",
    "xr_barrel": "XR Barrel (XR;B)",
    "raise_barrel": "Raise Barrel (R;B)",
    "ip_float_stab": "IP Float Stab (C;X-B)",
    "oop_xc_donk_lead": "OOP XC Donk Lead (X-C;B)",
}

POSITION_LABELS: Mapping[str, str] = {
    "IP": "In Position",
    "OOP": "Out of Position",
}

HERO_POSITION_ORDER: Sequence[str] = [
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

TEXTURE_ANY_KEY = "any"
TEXTURE_OPTIONS: Sequence[Mapping[str, str]] = [
    {"key": TEXTURE_ANY_KEY, "label": "All Textures"},
    *(
        {"key": spec.key, "label": spec.title}
        for spec in TURN_TEXTURE_SPECS
    ),
]
TEXTURE_ORDER = {option["key"]: index for index, option in enumerate(TEXTURE_OPTIONS)}


def load_turn_hand_matrix() -> dict:
    """Return aggregated hero hand distributions by turn bet sizing."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"turn_hand_matrix_{stake_policy.cache_token()}.json"

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("version") == CURRENT_VERSION:
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    data_paths.ensure_cache_dir()

    events = collect_turn_bet_events()
    payload = _aggregate(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def _aggregate(events: Iterable[Mapping[str, object]]) -> dict:
    scenario_map: Dict[Tuple[str, str, str, int, str, str], Dict[str, Dict[str, object]]] = {}
    hero_positions: set[str] = set()
    bet_lines: set[str] = set()
    positions: set[str] = set()
    player_counts: set[int] = set()
    texture_keys_seen: set[str] = set()
    preflop_keys_seen: set[str] = set()

    for event in events:
        primary = event.get("hand_primary")
        if not isinstance(primary, str) or primary not in HAND_TYPE_SET:
            primary = "Air"

        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        hero_position = str(event.get("hero_position") or "UNKNOWN")
        bet_line = str(event.get("bet_line") or "")
        in_position = str(event.get("position") or ("IP" if bool(event.get("in_position")) else "OOP"))

        player_count_value = event.get("player_count")
        try:
            player_count = int(player_count_value)
        except (TypeError, ValueError):
            continue
        if player_count <= 0:
            continue

        event_texture_keys = _event_texture_keys(event)
        texture_keys_seen.update(event_texture_keys)
        texture_keys_for_event = [TEXTURE_ANY_KEY, *event_texture_keys] if event_texture_keys else [TEXTURE_ANY_KEY]

        preflop_bucket_key = preflop_bucket(event.get("preflop_aggression_level"))
        preflop_keys_seen.add(preflop_bucket_key)
        preflop_keys_for_event = preflop_keys(event.get("preflop_aggression_level"))

        for texture_key in texture_keys_for_event:
            for preflop_key in preflop_keys_for_event:
                scenario_key = (hero_position, bet_line, in_position, player_count, texture_key, preflop_key)
                bucket_map = scenario_map.setdefault(scenario_key, _initial_bucket_map())
                for bucket_key in bucket_keys:
                    stats = bucket_map.get(bucket_key)
                    if stats is None:
                        continue
                    stats["events"] += 1
                    stats["categories"][primary] += 1
                    if bool(event.get("has_flush_draw")):
                        stats["categories"]["Flush Draw"] += 1
                    if bool(event.get("has_oesd_dg")):
                        stats["categories"]["OESD/DG"] += 1

        hero_positions.add(hero_position)
        if bet_line:
            bet_lines.add(bet_line)
        positions.add(in_position)
        player_counts.add(player_count)

    scenario_payload: List[dict] = []
    for (hero_position, bet_line, in_position, player_count, texture_key, preflop_key), bucket_map in sorted(
        scenario_map.items(),
        key=lambda item: (
            _hero_position_rank(item[0][0]),
            _bet_line_rank(item[0][1]),
            0 if item[0][2] == "IP" else 1,
            item[0][3],
            TEXTURE_ORDER.get(item[0][4], len(TEXTURE_ORDER)),
            PREFLOP_ORDER.get(item[0][5], len(PREFLOP_ORDER)),
        ),
    ):
        metrics = []
        for meta in BUCKET_METADATA:
            stats = bucket_map[meta.key]
            metrics.append(
                {
                    "bucket_key": meta.key,
                    "bucket_label": meta.label,
                    "events": stats["events"],
                    "categories": dict(stats["categories"]),
                }
            )
        scenario_payload.append(
            {
                "hero_position": hero_position,
                "bet_line": bet_line,
                "position": in_position,
                "player_count": player_count,
                "texture_key": texture_key,
                "preflop_key": preflop_key,
                "metrics": metrics,
            }
        )

    bucket_order = [meta.__dict__ for meta in BUCKET_METADATA]

    hand_types = [
        {"key": label, "label": label, "kind": "primary"}
        for label in PRIMARY_HAND_TYPES
    ] + [
        {"key": label, "label": label, "kind": "draw"}
        for label in DRAW_CATEGORIES
    ]

    groupings = [
        {
            "key": "grouped",
            "label": "Grouped View",
            "groups": [
                {"key": group_label, "label": group_label, "members": list(members)}
                for group_label, members in GROUP_DEFINITIONS
            ],
        }
    ]

    bet_line_options = [
        {"key": key, "label": BET_LINE_LABELS.get(key, key)}
        for key in sorted(bet_lines, key=_bet_line_rank)
    ]

    position_options = [
        {"key": key, "label": POSITION_LABELS.get(key, key)}
        for key in sorted(positions, key=lambda value: 0 if value == "IP" else 1)
    ]

    hero_positions_ordered = sorted(hero_positions, key=_hero_position_rank)

    return {
        "version": CURRENT_VERSION,
        "bucket_order": bucket_order,
        "hand_types": hand_types,
        "groupings": groupings,
        "betting_lines": bet_line_options,
        "positions": position_options,
        "hero_positions": hero_positions_ordered,
        "player_counts": sorted(player_counts),
        "textures": [
            option
            for option in TEXTURE_OPTIONS
            if option["key"] == TEXTURE_ANY_KEY or option["key"] in texture_keys_seen
        ],
        "preflop_categories": [
            option
            for option in PREFLOP_OPTIONS
            if option["key"] == PREFLOP_ANY_KEY or option["key"] in preflop_keys_seen
        ],
        "scenarios": scenario_payload,
    }


def _initial_bucket_map() -> Dict[str, Dict[str, object]]:
    return {
        meta.key: {
            "events": 0,
            "categories": {label: 0 for label in HAND_TYPE_ORDER},
        }
        for meta in BUCKET_METADATA
    }


def _bet_line_rank(key: str) -> int:
    ordering = list(BET_LINE_LABELS.keys())
    try:
        return ordering.index(key)
    except ValueError:
        return len(ordering)


def _event_texture_keys(event: Mapping[str, object]) -> list[str]:
    raw = event.get("turn_texture_keys")
    if isinstance(raw, (list, tuple, set)):
        textures = [str(value) for value in raw if isinstance(value, str) and value]
        if textures:
            return textures
    turn_cards = event.get("turn_cards") or event.get("board_turn")
    return turn_texture_keys(turn_cards)


def _hero_position_rank(label: str) -> int:
    try:
        return HERO_POSITION_ORDER.index(label)
    except ValueError:
        return len(HERO_POSITION_ORDER)


__all__ = ["load_turn_hand_matrix"]
CURRENT_VERSION = 1
