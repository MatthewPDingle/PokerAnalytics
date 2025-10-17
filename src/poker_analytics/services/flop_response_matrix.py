"""Aggregate villain responses to hero flop bets by bet size."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, MutableMapping, Optional, Sequence, Tuple

from poker_analytics.config import build_data_paths
from poker_analytics.data.bet_sizing import BET_SIZE_BUCKETS, BetSizeBucket, bucket_for_ratio
from poker_analytics.services.flop_response_matrix_builder import collect_flop_bet_events


@dataclass(frozen=True)
class BucketMeta:
    key: str
    label: str


BUCKET_METADATA: Sequence[BucketMeta] = tuple(
    BucketMeta(key=bucket.key, label=bucket.label) for bucket in BET_SIZE_BUCKETS
) + (
    BucketMeta(key="all_in", label="All-In"),
    BucketMeta(key="one_bb", label="1 BB"),
)

BUCKET_KEYS = [meta.key for meta in BUCKET_METADATA]

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

    data_paths = build_data_paths()
    cache_path = data_paths.cache_dir / "flop_response_matrix.json"

    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass

    data_paths.ensure_cache_dir()

    events = collect_flop_bet_events()
    if not events:
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
        "bucket_order": [meta.__dict__ for meta in BUCKET_METADATA],
        "bet_types": list(BET_TYPE_OPTIONS),
        "positions": list(POSITION_OPTIONS),
        "player_counts": sorted(player_counts),
        "hero_positions": hero_positions,
        "scenarios": scenarios,
    }
    return payload


def _aggregate_events(events: Iterable[Mapping[str, object]]) -> Tuple[List[dict], List[int], List[str]]:
    aggregate: MutableMapping[Tuple[str, str, str, int], MutableMapping[str, Dict[str, int]]] = defaultdict(
        lambda: {key: {"events": 0, "fold_events": 0, "call_events": 0, "raise_events": 0} for key in BUCKET_KEYS}
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

        bucket_key = _bucket_for_event(event)
        if bucket_key is None:
            continue

        outcome = event.get("villain_outcome")
        if not isinstance(outcome, str):
            responses = event.get("responses") or []
            outcome = _resolve_outcome(responses)

        bucket_metrics = aggregate[(hero_position, bet_type, position, player_count)][bucket_key]

        bucket_metrics["events"] += 1
        if outcome == "raise":
            bucket_metrics["raise_events"] += 1
        elif outcome == "call":
            bucket_metrics["call_events"] += 1
        else:
            bucket_metrics["fold_events"] += 1

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
                        "events": bucket_map[meta.key]["events"],
                        "fold_events": bucket_map[meta.key]["fold_events"],
                        "call_events": bucket_map[meta.key]["call_events"],
                        "raise_events": bucket_map[meta.key]["raise_events"],
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


def _bucket_for_event(event: Mapping[str, object]) -> Optional[str]:
    if bool(event.get("is_all_in")):
        return "all_in"
    if bool(event.get("is_one_bb")):
        return "one_bb"

    key = event.get("bucket_key")
    if isinstance(key, str):
        return key

    ratio_raw = event.get("ratio")
    try:
        ratio = float(ratio_raw) if ratio_raw is not None else None
    except (TypeError, ValueError):
        ratio = None

    bucket = bucket_for_ratio(ratio)
    if isinstance(bucket, BetSizeBucket):
        return bucket.key
    return None


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


__all__ = ["load_flop_response_matrix", "build_flop_response_payload"]
