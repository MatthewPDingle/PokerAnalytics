"""Aggregate villain responses to hero flop bets by bet size."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Dict, List, MutableMapping, Optional, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_bucket_utils import BUCKET_KEYS, BUCKET_METADATA, bucket_keys_for_event
from poker_analytics.services.flop_response_matrix_builder import collect_flop_bet_events

BET_TYPE_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "cbet", "label": "Continuation Bet"},
    {"key": "donk", "label": "Donk Bet"},
    {"key": "stab", "label": "Stab / Other"},
)

BET_TYPE_ORDER = {option["key"]: index for index, option in enumerate(BET_TYPE_OPTIONS)}

HERO_POSITION_ORDER = ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "UNKNOWN"]
HERO_POSITION_RANK = {value: index for index, value in enumerate(HERO_POSITION_ORDER)}

POSITION_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": "IP", "label": "In Position"},
    {"key": "OOP", "label": "Out of Position"},
)

POSITION_ORDER = {option["key"]: index for index, option in enumerate(POSITION_OPTIONS)}

LEGACY_CACHE_FILENAMES: Mapping[str, Sequence[str]] = {
    "cbet": ("flop_cbet_events.json", "cbet_events.json"),
    "donk": ("flop_donk_events.json", "donk_events.json"),
}


def load_flop_response_matrix() -> dict:
    """Return the aggregated payload used by the frontend heatmap."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"flop_response_matrix_{stake_policy.cache_token()}.json"

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
    if not events and stake_policy.is_unrestricted():
        for bet_type, filenames in LEGACY_CACHE_FILENAMES.items():
            events.extend(_load_events_for_type(bet_type, filenames))

    payload = build_flop_response_payload(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_flop_response_payload(events: Iterable[Mapping[str, object]]) -> dict:
    """Build the response payload from an iterable of raw events."""

    scenarios, player_counts, hero_positions = _aggregate_events(events)
    payload = {
        "version": CURRENT_VERSION,
        "bucket_order": [meta.__dict__ for meta in BUCKET_METADATA],
        "bet_types": list(BET_TYPE_OPTIONS),
        "positions": list(POSITION_OPTIONS),
        "player_counts": sorted(player_counts),
        "hero_positions": hero_positions,
        "scenarios": scenarios,
    }
    return payload


def _aggregate_events(events: Iterable[Mapping[str, object]]) -> Tuple[List[dict], List[int], List[str]]:
    aggregate: MutableMapping[
        Tuple[str, str, str, int],
        MutableMapping[str, Dict[str, float]],
    ] = defaultdict(
        lambda: {
            key: {
                "events": 0.0,
                "fold_events": 0.0,
                "call_events": 0.0,
                "raise_events": 0.0,
                "ratio_sum": 0.0,
                "total_added_flop_bb": 0.0,
                "total_added_all_bb": 0.0,
                "share_all_sum": 0.0,
                "breakeven_sum": 0.0,
            }
            for key in BUCKET_KEYS
        }
    )
    player_counts: set[int] = set()
    hero_positions: set[str] = set()

    for event in events:
        hero_position = event.get("hero_position")
        if not isinstance(hero_position, str) or not hero_position:
            hero_position = "UNKNOWN"
        hero_positions.add(hero_position)

        bet_type = _normalise_bet_type(event.get("bet_type"))
        if bet_type is None:
            continue

        position_field = event.get("position")
        if isinstance(position_field, str):
            position = position_field
        else:
            position = "IP" if bool(event.get("in_position")) else "OOP"
        player_count_raw = event.get("player_count")
        if player_count_raw is None:
            player_count_raw = event.get("flop_players")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            player_count = 0

        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        outcome = event.get("villain_outcome")
        if not isinstance(outcome, str):
            responses = event.get("responses") or []
            outcome = _resolve_outcome(responses)

        ratio_value: float
        try:
            ratio_raw = event.get("ratio")
            ratio_value = float(ratio_raw) if ratio_raw is not None else 0.0
        except (TypeError, ValueError):
            ratio_value = 0.0

        total_flop_bb = _safe_float(event.get("total_added_flop_bb"))
        total_all_bb = _safe_float(event.get("total_added_all_bb")) or total_flop_bb
        pot_before_bb = _safe_float(event.get("pot_before_bb"))
        share_all = (total_all_bb / pot_before_bb) if pot_before_bb > 0 else 0.0
        breakeven_pct = (ratio_value / (1.0 + ratio_value) * 100.0) if ratio_value > 0 else 0.0

        scenario_key = (hero_position, bet_type, position, player_count)
        bucket_map = aggregate[scenario_key]

        for bucket_key in bucket_keys:
            bucket_metrics = bucket_map[bucket_key]
            bucket_metrics["events"] += 1
            if outcome == "raise":
                bucket_metrics["raise_events"] += 1
            elif outcome == "call":
                bucket_metrics["call_events"] += 1
            else:
                bucket_metrics["fold_events"] += 1
            bucket_metrics["ratio_sum"] += ratio_value
            bucket_metrics["total_added_flop_bb"] += total_flop_bb
            bucket_metrics["total_added_all_bb"] += total_all_bb
            bucket_metrics["share_all_sum"] += share_all
            bucket_metrics["breakeven_sum"] += breakeven_pct

        if player_count:
            player_counts.add(player_count)

    scenarios = []
    for (hero_position, bet_type, position, player_count), bucket_map in sorted(
        aggregate.items(),
        key=lambda item: (
            HERO_POSITION_RANK.get(item[0][0], len(HERO_POSITION_RANK)),
            BET_TYPE_ORDER.get(item[0][1], len(BET_TYPE_ORDER)),
            POSITION_ORDER.get(item[0][2], len(POSITION_ORDER)),
            item[0][3],
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_type": bet_type,
                "position": position,
                "player_count": player_count,
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
                        "avg_added_flop_bb": (
                            bucket_map[meta.key]["total_added_flop_bb"] / bucket_map[meta.key]["events"]
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

    return scenarios, sorted(player_counts), hero_positions_sorted


def _resolve_outcome(responses: object) -> str:
    """Determine the aggregate villain outcome for an event."""

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


def _normalise_bet_type(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    # Align to canonical keys
    for option in BET_TYPE_OPTIONS:
        if lowered == option["key"]:
            return option["key"]
    return None


def _normalise_response(value: object) -> Optional[str]:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"call", "raise", "fold"}:
            return lowered
    return None


def _load_events_for_type(bet_type: str, filenames: Sequence[str]) -> list[dict]:
    """Load cached events for a specific bet classification."""

    data_paths = build_data_paths()
    candidates: List[Path] = [data_paths.cache_dir / name for name in filenames]
    legacy_root = Path("analysis/cache")
    candidates.extend(legacy_root / name for name in filenames)

    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                contents = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(contents, list):
            continue
        events: list[dict] = []
        for entry in contents:
            if isinstance(entry, Mapping):
                record = dict(entry)
                record["bet_type"] = bet_type
                events.append(record)
        if events:
            return events
    return []


def load_flop_pot_contribution() -> dict:
    """Return average pot contribution per bet-size bucket."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / f"flop_pot_contribution_{stake_policy.cache_token()}.json"

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
    payload = build_flop_pot_contribution_payload(events)

    try:
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        pass

    return payload


def build_flop_pot_contribution_payload(events: Iterable[Mapping[str, object]]) -> dict:
    scenarios_map: MutableMapping[Tuple[str, str, str, int], MutableMapping[str, Dict[str, float]]] = defaultdict(
        lambda: {key: {"events": 0, "sum_added_bb": 0.0} for key in BUCKET_KEYS}
    )

    player_counts: set[int] = set()
    hero_positions: set[str] = set()

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

        bet_type = _normalise_bet_type(event.get("bet_type"))
        if bet_type is None:
            continue

        position_field = event.get("position")
        if isinstance(position_field, str):
            position = position_field
        else:
            position = "IP" if bool(event.get("in_position")) else "OOP"

        player_count_raw = event.get("player_count")
        if player_count_raw is None:
            player_count_raw = event.get("flop_players")
        try:
            player_count = int(player_count_raw)
        except (TypeError, ValueError):
            player_count = 0

        if player_count:
            player_counts.add(player_count)

        bucket_keys = bucket_keys_for_event(event)
        if not bucket_keys:
            continue

        bucket_map = scenarios_map[(hero_position, bet_type, position, player_count)]
        for bucket_key in bucket_keys:
            bucket_entry = bucket_map[bucket_key]
            bucket_entry["events"] += 1
            bucket_entry["sum_added_bb"] += added_bb

    scenarios = []
    for (hero_position, bet_type, position, player_count), bucket_map in sorted(
        scenarios_map.items(),
        key=lambda item: (
            HERO_POSITION_RANK.get(item[0][0], len(HERO_POSITION_RANK)),
            BET_TYPE_ORDER.get(item[0][1], len(BET_TYPE_ORDER)),
            POSITION_ORDER.get(item[0][2], len(POSITION_ORDER)),
            item[0][3],
        ),
    ):
        scenarios.append(
            {
                "hero_position": hero_position,
                "bet_type": bet_type,
                "position": position,
                "player_count": player_count,
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
        "bet_types": list(BET_TYPE_OPTIONS),
        "positions": list(POSITION_OPTIONS),
        "player_counts": sorted(player_counts),
        "hero_positions": sorted(
            hero_positions,
            key=lambda value: HERO_POSITION_RANK.get(value, len(HERO_POSITION_RANK)),
        ),
        "scenarios": scenarios,
    }


__all__ = [
    "load_flop_response_matrix",
    "build_flop_response_payload",
    "load_flop_pot_contribution",
    "build_flop_pot_contribution_payload",
]
CURRENT_VERSION = 4
