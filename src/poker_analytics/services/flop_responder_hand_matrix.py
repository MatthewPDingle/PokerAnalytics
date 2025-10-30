"""Aggregate responder hand classifications by bet-size bucket."""

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
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA, BUCKET_KEYS, bucket_keys_for_event
from poker_analytics.services.flop_response_matrix_builder import collect_flop_bet_events

HAND_TYPE_ORDER: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES)
HAND_TYPE_SET = set(HAND_TYPE_ORDER)

BET_TYPE_ORDER: Sequence[str] = ("cbet", "donk", "stab")
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

RESPONSE_TYPE_ORDER: Sequence[str] = ("call", "raise")
RESPONSE_TYPE_LABELS: Mapping[str, str] = {"call": "Call", "raise": "Raise"}
BET_TYPE_LABELS: Mapping[str, str] = {
    "cbet": "Continuation Bet",
    "donk": "Donk Bet",
    "stab": "Stab / Other",
}


def load_flop_responder_hand_matrix() -> dict:
    """Return aggregated responder hand distributions by flop bet sizing."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"flop_responder_hand_matrix_{stake_policy.cache_token()}.json"

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("version") == CURRENT_VERSION:
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    data_paths.ensure_cache_dir()

    events = collect_flop_bet_events()
    payload = _aggregate(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def _aggregate(events: Iterable[Mapping[str, object]]) -> dict:
    scenario_map: Dict[
        Tuple[str, str, str, int, str],
        MutableMapping[str, Dict[str, object]],
    ] = {}

    hero_positions: set[str] = set()
    bet_types: set[str] = set()
    positions: set[str] = set()
    player_counts: set[int] = set()
    response_types: set[str] = set()

    for event in events:
        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        hero_position = str(event.get("hero_position") or "UNKNOWN")
        bet_type = _normalise_bet_type(event.get("bet_type"))
        position = "IP" if bool(event.get("in_position")) else "OOP"
        player_count_raw = event.get("player_count")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            continue
        if not bet_type or player_count <= 0:
            continue

        responses = event.get("responses")
        if not isinstance(responses, Iterable):
            continue

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

            scenario_key = (hero_position, bet_type, position, player_count, response_type)
            bucket_map = scenario_map.setdefault(scenario_key, _initial_bucket_map())

            hero_positions.add(hero_position)
            bet_types.add(bet_type)
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
    for (hero_position, bet_type, position, player_count, response_type), bucket_map in sorted(
        scenario_map.items(),
        key=lambda item: (
            _hero_position_rank(item[0][0]),
            _bet_type_rank(item[0][1]),
            _position_rank(item[0][2]),
            item[0][3],
            _response_type_rank(item[0][4]),
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_type": bet_type,
                "position": position,
                "player_count": player_count,
                "response_type": response_type,
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

    bet_type_options = [
        {"key": key, "label": BET_TYPE_LABELS.get(key, key.title())}
        for key in sorted(bet_types, key=_bet_type_rank)
    ]

    return {
        "version": CURRENT_VERSION,
        "bucket_order": bucket_order,
        "hand_types": hand_types,
        "groupings": groupings,
        "bet_types": bet_type_options,
        "positions": [
            {"key": key, "label": key if key in POSITION_ORDER else key.title()}
            for key in sorted(positions, key=_position_rank)
        ],
        "hero_positions": sorted(hero_positions, key=_hero_position_rank),
        "player_counts": sorted(player_counts),
        "response_types": response_type_options,
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
    try:
        return HERO_POSITION_ORDER.index(value)
    except ValueError:
        return len(HERO_POSITION_ORDER)


def _response_type_rank(value: str) -> int:
    try:
        return RESPONSE_TYPE_ORDER.index(value)
    except ValueError:
        return len(RESPONSE_TYPE_ORDER)


def _normalise_bet_type(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in BET_TYPE_ORDER:
            return lowered
    return None


def _normalise_response_type(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in RESPONSE_TYPE_ORDER:
            return lowered
    return None


__all__ = ["load_flop_responder_hand_matrix"]
CURRENT_VERSION = 1
