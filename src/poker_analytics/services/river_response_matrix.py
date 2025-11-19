"""Aggregate villain responses to river bets by bet size."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Dict, List, MutableMapping, Optional, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.data.textures import RIVER_TEXTURE_SPECS, river_texture_keys
from poker_analytics.services.flop_bucket_utils import BUCKET_KEYS, BUCKET_METADATA, bucket_keys_for_event
from poker_analytics.services.flop_preflop_utils import (
    PREFLOP_ANY_KEY,
    PREFLOP_OPTIONS,
    PREFLOP_ORDER,
    preflop_bucket,
    preflop_keys,
)
from poker_analytics.services.flop_response_matrix_builder import collect_river_bet_events

BETTING_LINE_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "triple_barrel", "label": "Triple Barrel (B;B;B)"},
    {"key": "bet_check_bet", "label": "Bet Check Bet (B;X;B)"},
    {"key": "delayed_double", "label": "Delayed Double (X;B;B)"},
    {"key": "river_stab", "label": "River Stab (X;X;B)"},
    {"key": "float_river_stab", "label": "Float Flop / River Stab (C;X;B)"},
    {"key": "raise_barrel", "label": "Raise Flop / Barrel Turn & River (R;B;B)"},
)

BETTING_LINE_ORDER = {option["key"]: index for index, option in enumerate(BETTING_LINE_OPTIONS)}

HERO_POSITION_ORDER = ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "UNKNOWN"]
HERO_POSITION_RANK = {value: index for index, value in enumerate(HERO_POSITION_ORDER)}

POSITION_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "IP", "label": "In Position"},
    {"key": "OOP", "label": "Out of Position"},
)

POSITION_ORDER = {option["key"]: index for index, option in enumerate(POSITION_OPTIONS)}

TEXTURE_ANY_KEY = "any"
TEXTURE_OPTIONS: Sequence[Mapping[str, str]] = [
    {"key": TEXTURE_ANY_KEY, "label": "All Textures"},
    *(
        {"key": spec.key, "label": spec.title}
        for spec in RIVER_TEXTURE_SPECS
    ),
]
TEXTURE_ORDER = {option["key"]: index for index, option in enumerate(TEXTURE_OPTIONS)}

SPR_BUCKET_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "<=1", "label": "<= 1"},
    {"key": "1-2", "label": "1-2"},
    {"key": "2-4", "label": "2-4"},
    {"key": "4-6", "label": "4-6"},
    {"key": "6-10", "label": "6-10"},
    {"key": "10+", "label": "10+"},
)
SPR_BUCKET_ORDER = {"any": 0, **{option["key"]: index + 1 for index, option in enumerate(SPR_BUCKET_OPTIONS)}}
SPR_BUCKET_KEYS = set(SPR_BUCKET_ORDER.keys())


def _load_cached_payload(cache_dir: Path, filename: str, *, source: str | None = None) -> dict | None:
    if source:
        candidates = [
            cache_dir / source / filename,
            cache_dir / filename,
        ]
    else:
        candidates = [cache_dir / filename]

    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("version") == CURRENT_VERSION:
            return payload
    return None


def load_river_response_matrix(source: str | None = None) -> dict:
    """Return the aggregated payload used by the frontend heatmap."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    filename = f"river_response_matrix_{stake_policy.cache_token()}.json"

    cached = _load_cached_payload(data_paths.cache_dir, filename, source=source)
    if cached is not None:
        return cached

    if source is not None:
        return build_river_response_payload([])

    data_paths.ensure_cache_dir()

    events = collect_river_bet_events()
    payload = build_river_response_payload(events)

    try:
        cache_path = data_paths.cache_dir / filename
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_river_response_payload(events: Iterable[Mapping[str, object]]) -> dict:
    """Build the response payload from an iterable of raw events."""

    (
        scenarios,
        player_counts,
        hero_positions,
        texture_keys_seen,
        preflop_keys_seen,
        spr_buckets_seen,
    ) = _aggregate_events(events)
    payload = {
        "version": CURRENT_VERSION,
        "bucket_order": [meta.__dict__ for meta in BUCKET_METADATA],
        "betting_lines": list(BETTING_LINE_OPTIONS),
        "positions": list(POSITION_OPTIONS),
        "player_counts": sorted(player_counts),
        "hero_positions": hero_positions,
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
    return payload


def _aggregate_events(events: Iterable[Mapping[str, object]]) -> Tuple[List[dict], List[int], List[str], set[str], set[str], set[str]]:
    aggregate: MutableMapping[
        Tuple[str, str, str, int, str, str, str],
        MutableMapping[str, Dict[str, float]],
    ] = defaultdict(
        lambda: {
            key: {
                "events": 0.0,
                "fold_events": 0.0,
                "call_events": 0.0,
                "raise_events": 0.0,
                "ratio_sum": 0.0,
                "total_added_river_bb": 0.0,
                "total_added_all_bb": 0.0,
                "share_all_sum": 0.0,
                "breakeven_sum": 0.0,
            }
            for key in BUCKET_KEYS
        }
    )
    player_counts: set[int] = set()
    hero_positions: set[str] = set()
    texture_keys_seen: set[str] = set()
    preflop_keys_seen: set[str] = set()
    spr_buckets_seen: set[str] = set()

    for event in events:
        hero_position = event.get("hero_position")
        if not isinstance(hero_position, str) or not hero_position:
            hero_position = "UNKNOWN"
        hero_positions.add(hero_position)

        bet_line = _normalise_bet_line(event.get("bet_line"))
        if bet_line is None:
            continue

        position_field = event.get("position")
        position = position_field if isinstance(position_field, str) else "IP" if bool(event.get("in_position")) else "OOP"
        player_count_raw = event.get("player_count")
        if player_count_raw is None:
            player_count_raw = event.get("river_players")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            player_count = 0

        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        event_texture_keys = _event_texture_keys(event)
        texture_keys_for_event = [TEXTURE_ANY_KEY, *event_texture_keys] if event_texture_keys else [TEXTURE_ANY_KEY]
        preflop_keys_for_event = preflop_keys(event.get("preflop_aggression_level"))

        outcome = event.get("villain_outcome")
        if not isinstance(outcome, str):
            responses = event.get("responses") or []
            outcome = _resolve_outcome(responses)

        ratio_value = _safe_float(event.get("ratio"))

        total_river_bb = _safe_float(event.get("total_added_river_bb"))
        total_all_bb = _safe_float(event.get("total_added_all_bb")) or total_river_bb
        pot_before_bb = _safe_float(event.get("pot_before_bb"))
        share_all = (total_all_bb / pot_before_bb) if pot_before_bb > 0 else 0.0
        breakeven_pct = (ratio_value / (1.0 + ratio_value) * 100.0) if ratio_value > 0 else 0.0

        if player_count:
            player_counts.add(player_count)
        texture_keys_seen.update(event_texture_keys)
        preflop_keys_seen.add(preflop_bucket(event.get("preflop_aggression_level")))

        spr_bucket_raw = event.get("spr_bucket")
        spr_bucket_value = spr_bucket_raw if isinstance(spr_bucket_raw, str) and spr_bucket_raw in SPR_BUCKET_KEYS else None
        spr_bucket_keys_for_event = ["any"]
        if spr_bucket_value and spr_bucket_value != "any":
            spr_bucket_keys_for_event.append(spr_bucket_value)
            spr_buckets_seen.add(spr_bucket_value)

        for texture_key in texture_keys_for_event:
            for preflop_key in preflop_keys_for_event:
                for spr_key in spr_bucket_keys_for_event:
                    scenario_key = (hero_position, bet_line, position, player_count, texture_key, preflop_key, spr_key)
                    bucket_map = aggregate[scenario_key]

                    for bucket_key in bucket_keys:
                        metrics = bucket_map[bucket_key]
                        metrics["events"] += 1
                        if outcome == "raise":
                            metrics["raise_events"] += 1
                        elif outcome == "call":
                            metrics["call_events"] += 1
                        else:
                            metrics["fold_events"] += 1
                        metrics["ratio_sum"] += ratio_value
                        metrics["total_added_river_bb"] += total_river_bb
                        metrics["total_added_all_bb"] += total_all_bb
                        metrics["share_all_sum"] += share_all
                        metrics["breakeven_sum"] += breakeven_pct

    scenarios: List[dict] = []
    for (
        hero_position,
        bet_line,
        position,
        player_count,
        texture_key,
        preflop_key,
        spr_bucket,
    ), bucket_map in sorted(
        aggregate.items(),
        key=lambda item: (
            HERO_POSITION_RANK.get(item[0][0], len(HERO_POSITION_RANK)),
            BETTING_LINE_ORDER.get(item[0][1], len(BETTING_LINE_ORDER)),
            POSITION_ORDER.get(item[0][2], len(POSITION_ORDER)),
            item[0][3],
            TEXTURE_ORDER.get(item[0][4], len(TEXTURE_ORDER)),
            PREFLOP_ORDER.get(item[0][5], len(PREFLOP_ORDER)),
            SPR_BUCKET_ORDER.get(item[0][6], len(SPR_BUCKET_ORDER)),
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_line": bet_line,
                "position": position,
                "player_count": player_count,
                "texture_key": texture_key,
                "preflop_key": preflop_key,
                "spr_bucket": spr_bucket,
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
                        "avg_added_river_bb": (
                            bucket_map[meta.key]["total_added_river_bb"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                        "avg_added_all_bb": (
                            bucket_map[meta.key]["total_added_all_bb"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                        "avg_share_all": (
                            bucket_map[meta.key]["share_all_sum"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                        "avg_breakeven_pct": (
                            bucket_map[meta.key]["breakeven_sum"] / bucket_map[meta.key]["events"]
                            if bucket_map[meta.key]["events"]
                            else 0.0
                        ),
                    }
                    for meta in BUCKET_METADATA
                ],
            }
        )

    hero_positions_sorted = sorted(
        hero_positions,
        key=lambda value: HERO_POSITION_RANK.get(value, len(HERO_POSITION_RANK)),
    )

    return (
        scenarios,
        sorted(player_counts),
        hero_positions_sorted,
        texture_keys_seen,
        preflop_keys_seen,
        set(spr_buckets_seen),
    )


def _event_texture_keys(event: Mapping[str, object]) -> list[str]:
    raw = event.get("river_texture_keys")
    if isinstance(raw, (list, tuple, set)):
        textures = [str(value) for value in raw if isinstance(value, str) and value]
        if textures:
            return textures
    river_text = event.get("river_cards") or event.get("board_river")
    return river_texture_keys(river_text)


def _resolve_outcome(responses: object) -> str:
    outcome = "fold"
    if not isinstance(responses, Iterable):
        return outcome

    has_call = False
    for response in responses:
        if not isinstance(response, Mapping):
            continue
        result = _normalise_response(response.get("response"))
        if result == "raise":
            return "raise"
        if result == "call":
            has_call = True
    if has_call:
        return "call"
    return outcome


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalise_bet_line(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    for option in BETTING_LINE_OPTIONS:
        if lowered == option["key"]:
            return option["key"]
    return None


def _normalise_response(value: object) -> Optional[str]:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"call", "raise", "fold"}:
            return lowered
    return None


def load_river_pot_contribution(source: str | None = None) -> dict:
    """Return average pot contribution per bet-size bucket for river bets."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    filename = f"river_pot_contribution_{stake_policy.cache_token()}.json"

    cached = _load_cached_payload(data_paths.cache_dir, filename, source=source)
    if cached is not None:
        return cached

    if source is not None:
        return build_river_pot_contribution_payload([])

    data_paths.ensure_cache_dir()

    events = collect_river_bet_events()
    payload = build_river_pot_contribution_payload(events)

    try:
        cache_path = data_paths.cache_dir / filename
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_river_pot_contribution_payload(events: Iterable[Mapping[str, object]]) -> dict:
    scenarios_map: MutableMapping[
        Tuple[str, str, str, int, str, str],
        MutableMapping[str, Dict[str, float]],
    ] = defaultdict(lambda: {key: {"events": 0, "sum_added_bb": 0.0} for key in BUCKET_KEYS})

    player_counts: set[int] = set()
    hero_positions: set[str] = set()
    texture_keys_seen: set[str] = set()
    preflop_keys_seen: set[str] = set()

    for event in events:
        added_bb_raw = event.get("total_added_all_bb")
        try:
            added_bb = float(added_bb_raw)
        except (TypeError, ValueError):
            continue

        hero_position = event.get("hero_position")
        if not isinstance(hero_position, str) or not hero_position:
            hero_position = "UNKNOWN"
        hero_positions.add(hero_position)

        bet_line = _normalise_bet_line(event.get("bet_line"))
        if bet_line is None:
            continue

        position_field = event.get("position")
        position = position_field if isinstance(position_field, str) else "IP" if bool(event.get("in_position")) else "OOP"

        player_count_raw = event.get("player_count")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            player_count = 0

        if player_count:
            player_counts.add(player_count)

        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        event_texture_keys = _event_texture_keys(event)
        texture_keys_seen.update(event_texture_keys)
        texture_keys_for_event = [TEXTURE_ANY_KEY, *event_texture_keys] if event_texture_keys else [TEXTURE_ANY_KEY]

        preflop_bucket_key = preflop_bucket(event.get("preflop_aggression_level"))
        preflop_keys_seen.add(preflop_bucket_key)
        preflop_keys_for_event = preflop_keys(event.get("preflop_aggression_level"))

        for texture_key in texture_keys_for_event:
            for preflop_key in preflop_keys_for_event:
                bucket_map = scenarios_map[(hero_position, bet_line, position, player_count, texture_key, preflop_key)]
                for bucket_key in bucket_keys:
                    bucket_entry = bucket_map[bucket_key]
                    bucket_entry["events"] += 1
                    bucket_entry["sum_added_bb"] += added_bb

    scenarios = []
    for (hero_position, bet_line, position, player_count, texture_key, preflop_key), bucket_map in sorted(
        scenarios_map.items(),
        key=lambda item: (
            HERO_POSITION_RANK.get(item[0][0], len(HERO_POSITION_RANK)),
            BETTING_LINE_ORDER.get(item[0][1], len(BETTING_LINE_ORDER)),
            POSITION_ORDER.get(item[0][2], len(POSITION_ORDER)),
            item[0][3],
            TEXTURE_ORDER.get(item[0][4], len(TEXTURE_ORDER)),
            PREFLOP_ORDER.get(item[0][5], len(PREFLOP_ORDER)),
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_line": bet_line,
                "position": position,
                "player_count": player_count,
                "texture_key": texture_key,
                "preflop_key": preflop_key,
                "metrics": [
                    {
                        "bucket_key": meta.key,
                        "bucket_label": meta.label,
                        "events": int(bucket_map[meta.key]["events"]),
                        "avg_added_bb": (
                            bucket_map[meta.key]["sum_added_bb"] / bucket_map[meta.key]["events"]
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
        "bucket_order": [meta.__dict__ for meta in BUCKET_METADATA],
        "betting_lines": list(BETTING_LINE_OPTIONS),
        "positions": list(POSITION_OPTIONS),
        "player_counts": sorted(player_counts),
        "hero_positions": sorted(
            hero_positions,
            key=lambda value: HERO_POSITION_RANK.get(value, len(HERO_POSITION_ORDER)),
        ),
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
        "scenarios": scenarios,
    }


__all__ = [
    "load_river_response_matrix",
    "build_river_response_payload",
    "load_river_pot_contribution",
    "build_river_pot_contribution_payload",
]
CURRENT_VERSION = 2
