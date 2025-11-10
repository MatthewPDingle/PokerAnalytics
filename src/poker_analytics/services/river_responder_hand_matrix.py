"""Aggregate responder hand classifications by river bet-size bucket."""

from __future__ import annotations

import json
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.flop_hand_categories import (
    DRAW_CATEGORIES,
    GROUP_DEFINITIONS,
    PRIMARY_HAND_TYPES,
)
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.data.textures import RIVER_TEXTURE_SPECS, river_texture_keys
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA, BUCKET_KEYS, bucket_keys_for_event
from poker_analytics.services.flop_preflop_utils import (
    PREFLOP_ANY_KEY,
    PREFLOP_OPTIONS,
    PREFLOP_ORDER,
    preflop_bucket,
    preflop_keys,
)
from poker_analytics.services.flop_response_matrix_builder import collect_river_bet_events

HAND_TYPE_ORDER: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES)
HAND_TYPE_SET = set(HAND_TYPE_ORDER)

BET_LINE_ORDER: Sequence[str] = (
    "triple_barrel",
    "bet_check_bet",
    "delayed_double",
    "river_stab",
    "float_river_stab",
    "raise_barrel",
)
POSITION_ORDER: Sequence[str] = ("IP", "OOP")
HERO_POSITION_ORDER: Sequence[str] = (
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
)

TEXTURE_ANY_KEY = "any"
TEXTURE_OPTIONS: Sequence[Mapping[str, str]] = [
    {"key": TEXTURE_ANY_KEY, "label": "All Textures"},
    *(
        {"key": spec.key, "label": spec.title}
        for spec in RIVER_TEXTURE_SPECS
    ),
]
TEXTURE_ORDER = {option["key"]: index for index, option in enumerate(TEXTURE_OPTIONS)}

RESPONSE_TYPE_ORDER: Sequence[str] = ("call", "raise")
RESPONSE_TYPE_LABELS: Mapping[str, str] = {"call": "Call", "raise": "Raise"}
BET_LINE_LABELS: Mapping[str, str] = {
    "triple_barrel": "Triple Barrel (B;B;B)",
    "bet_check_bet": "Bet Check Bet (B;X;B)",
    "delayed_double": "Delayed Double (X;B;B)",
    "river_stab": "River Stab (X;X;B)",
    "float_river_stab": "Float Flop / River Stab (C;X;B)",
    "raise_barrel": "Raise Flop / Barrel Turn & River (R;B;B)",
}

SPR_ANY_KEY = "any"
SPR_BUCKET_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "<=1", "label": "<= 1"},
    {"key": "1-2", "label": "1-2"},
    {"key": "2-4", "label": "2-4"},
    {"key": "4-6", "label": "4-6"},
    {"key": "6-10", "label": "6-10"},
    {"key": "10+", "label": "10+"},
)
SPR_BUCKET_ORDER = {SPR_ANY_KEY: 0, **{option["key"]: index + 1 for index, option in enumerate(SPR_BUCKET_OPTIONS)}}
SPR_BUCKET_KEYS = {option["key"] for option in SPR_BUCKET_OPTIONS}


def load_river_responder_hand_matrix() -> dict:
    """Return aggregated responder hand distributions by river bet sizing."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"river_responder_hand_matrix_{stake_policy.cache_token()}.json"

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("version") == CURRENT_VERSION:
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    data_paths.ensure_cache_dir()

    events = collect_river_bet_events()
    payload = _aggregate(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def _aggregate(events: Iterable[Mapping[str, object]]) -> dict:
    scenario_map: Dict[
        Tuple[str, str, str, int, str, str, str],
        MutableMapping[str, Dict[str, object]],
    ] = {}

    hero_positions: set[str] = set()
    bet_lines: set[str] = set()
    positions: set[str] = set()
    player_counts: set[int] = set()
    response_types: set[str] = set()
    texture_keys_seen: set[str] = set()
    preflop_keys_seen: set[str] = set()
    spr_buckets_seen: set[str] = set()

    for event in events:
        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        hero_position = str(event.get("hero_position") or "UNKNOWN")
        bet_line = _normalise_bet_line(event.get("bet_line"))
        position = str(event.get("position") or ("IP" if bool(event.get("in_position")) else "OOP"))
        player_count_raw = event.get("player_count")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            continue
        if not bet_line or player_count <= 0:
            continue

        responses = event.get("responses")
        if not isinstance(responses, Iterable):
            continue

        event_texture_keys = _event_texture_keys(event)
        texture_keys_seen.update(event_texture_keys)
        texture_keys_for_event = [TEXTURE_ANY_KEY, *event_texture_keys] if event_texture_keys else [TEXTURE_ANY_KEY]

        preflop_bucket_key = preflop_bucket(event.get("preflop_aggression_level"))
        preflop_keys_seen.add(preflop_bucket_key)
        preflop_keys_for_event = preflop_keys(event.get("preflop_aggression_level"))

        spr_bucket_raw = event.get("spr_bucket")
        spr_bucket_value = str(spr_bucket_raw).strip() if isinstance(spr_bucket_raw, str) else None
        if spr_bucket_value and spr_bucket_value not in SPR_BUCKET_KEYS:
            spr_bucket_value = None
        spr_bucket_keys = [SPR_ANY_KEY]
        if spr_bucket_value:
            spr_bucket_keys.append(spr_bucket_value)
            spr_buckets_seen.add(spr_bucket_value)

        for response in responses:
            if not isinstance(response, Mapping):
                continue
            response_type = _normalise_response_type(response.get("response"))
            if response_type is None:
                continue
            primary = response.get("hand_primary")
            if not isinstance(primary, str) or primary not in HAND_TYPE_SET:
                continue
            has_flush_draw = bool(response.get("has_flush_draw"))
            has_oesd_dg = bool(response.get("has_oesd_dg"))

            for texture_key in texture_keys_for_event:
                for preflop_key in preflop_keys_for_event:
                    for spr_bucket_key in spr_bucket_keys:
                        scenario_key = (
                            hero_position,
                            bet_line,
                            position,
                            player_count,
                            response_type,
                            texture_key,
                            preflop_key,
                            spr_bucket_key,
                        )
                        bucket_map = scenario_map.setdefault(scenario_key, _initial_bucket_map())

                        hero_positions.add(hero_position)
                        bet_lines.add(bet_line)
                        positions.add(position)
                        player_counts.add(player_count)
                        response_types.add(response_type)

                        for bucket_key in bucket_keys:
                            stats = bucket_map.get(bucket_key)
                            if stats is None:
                                continue
                            stats["events"] += 1
                            stats["categories"][primary] += 1
                            if has_flush_draw:
                                stats["categories"]["Flush Draw"] += 1
                            if has_oesd_dg:
                                stats["categories"]["OESD/DG"] += 1

    scenarios: List[dict] = []
    for (
        hero_position,
        bet_line,
        position,
        player_count,
        response_type,
        texture_key,
        preflop_key,
        spr_bucket,
    ), bucket_map in sorted(
        scenario_map.items(),
        key=lambda item: (
            _hero_position_rank(item[0][0]),
            _bet_line_rank(item[0][1]),
            _position_rank(item[0][2]),
            item[0][3],
            _response_type_rank(item[0][4]),
            TEXTURE_ORDER.get(item[0][5], len(TEXTURE_ORDER)),
            PREFLOP_ORDER.get(item[0][6], len(PREFLOP_ORDER)),
            SPR_BUCKET_ORDER.get(item[0][7], len(SPR_BUCKET_ORDER)),
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_line": bet_line,
                "position": position,
                "player_count": player_count,
                "response_type": response_type,
                "texture_key": texture_key,
                "preflop_key": preflop_key,
                "spr_bucket": spr_bucket,
                "metrics": [
                    {
                        "bucket_key": meta.key,
                        "bucket_label": meta.label,
                        "events": bucket_map[meta.key]["events"],
                        "categories": dict(bucket_map[meta.key]["categories"]),
                    }
                    for meta in BUCKET_METADATA
                ],
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
                {"key": label, "label": label, "members": list(members)}
                for label, members in GROUP_DEFINITIONS
            ],
        }
    ]

    response_type_options = [
        {"key": key, "label": RESPONSE_TYPE_LABELS.get(key, key.title())}
        for key in RESPONSE_TYPE_ORDER
        if key in response_types
    ]

    bet_line_options = [
        {"key": key, "label": BET_LINE_LABELS.get(key, key)}
        for key in sorted(bet_lines, key=_bet_line_rank)
    ]

    return {
        "version": CURRENT_VERSION,
        "bucket_order": bucket_order,
        "hand_types": hand_types,
        "groupings": groupings,
        "betting_lines": bet_line_options,
        "positions": [
            {"key": key, "label": key if key in POSITION_ORDER else key.title()}
            for key in sorted(positions, key=_position_rank)
        ],
        "hero_positions": sorted(hero_positions, key=_hero_position_rank),
        "player_counts": sorted(player_counts),
        "response_types": response_type_options,
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
        "spr_buckets": [
            option
            for option in SPR_BUCKET_OPTIONS
            if option["key"] in spr_buckets_seen
        ],
        "scenarios": scenarios,
    }


def _initial_bucket_map() -> Dict[str, Dict[str, object]]:
    return {
        meta.key: {
            "events": 0,
            "categories": {label: 0 for label in HAND_TYPE_ORDER},
        }
        for meta in BUCKET_METADATA
    }


def _bet_line_rank(value: str) -> int:
    try:
        return BET_LINE_ORDER.index(value)
    except ValueError:
        return len(BET_LINE_ORDER)


def _position_rank(value: str) -> int:
    try:
        return POSITION_ORDER.index(value)
    except ValueError:
        return len(POSITION_ORDER)


def _hero_position_rank(value: str) -> int:
    try:
        return HERO_POSITION_ORDER.index(value)
    except ValueError:
        return len(HERO_POSITION_ORDER)


def _response_type_rank(value: str) -> int:
    try:
        return RESPONSE_TYPE_ORDER.index(value)
    except ValueError:
        return len(RESPONSE_TYPE_ORDER)


def _event_texture_keys(event: Mapping[str, object]) -> list[str]:
    raw = event.get("river_texture_keys")
    if isinstance(raw, (list, tuple, set)):
        textures = [str(value) for value in raw if isinstance(value, str) and value]
        if textures:
            return textures
    river_cards = event.get("river_cards") or event.get("board_river")
    return river_texture_keys(river_cards)


def _normalise_bet_line(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in BET_LINE_ORDER:
            return lowered
    return None


def _normalise_response_type(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in RESPONSE_TYPE_ORDER:
            return lowered
    return None


__all__ = ["load_river_responder_hand_matrix"]
CURRENT_VERSION = 2
