"""Dynamic aggregation for arbitrary betting lines."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from poker_analytics.config import build_data_paths
from poker_analytics.data.flop_hand_categories import DRAW_CATEGORIES, PRIMARY_HAND_TYPES
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_bucket_utils import BUCKET_METADATA
from poker_analytics.services.flop_response_matrix_builder import collect_line_events
from poker_analytics.services.line_descriptor import descriptor_fingerprint, parse_line_descriptor

CURRENT_VERSION = 2

HAND_TYPE_KEYS: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES)
HAND_TYPE_SET = set(HAND_TYPE_KEYS)
BET_ACTION_TO_TYPE = {
    "cbet": "cbet",
    "donk": "donk",
    "stab": "stab",
    "lead": "stab",
    "probe": "stab",
}


@dataclass
class CompiledFilters:
    response_types: Optional[set[str]] = None
    bet_types: Optional[set[str]] = None
    positions: Optional[set[str]] = None
    require_heads_up: bool = False
    require_multiway: bool = False
    bucket_keys: Optional[set[str]] = None
    ratio_min: Optional[float] = None
    ratio_max: Optional[float] = None
    exclude_hero: bool = False
    texture_keys: Optional[set[str]] = None


def query_line(
    payload: Mapping[str, object],
    *,
    events: Optional[Iterable[Mapping[str, object]]] = None,
) -> dict:
    """Aggregate responder and response metrics for a line descriptor."""

    descriptor = parse_line_descriptor(payload)
    raw_filters = payload.get("filters") if isinstance(payload, Mapping) else None
    request_filters: dict[str, Any] = {}
    if isinstance(raw_filters, Mapping):
        request_filters = {str(key): value for key, value in raw_filters.items()}

    filters = _compile_filters(descriptor, request_filters)
    stake_policy = StakePolicy.from_environment()
    descriptor_fingerprint_value = descriptor_fingerprint(descriptor)
    cache_fingerprint = _fingerprint_with_filters(descriptor_fingerprint_value, request_filters)
    cache_path = _resolve_cache_path(cache_fingerprint, stake_policy)

    cached = _read_cache(cache_path)
    if cached is not None:
        return cached

    source_events = list(events) if events is not None else collect_line_events()
    filtered_events = [event for event in source_events if _matches_filters(event, filters)]

    payload_dict = _build_payload(
        descriptor,
        stake_policy,
        filters,
        filtered_events,
        cache_fingerprint,
        request_filters,
        descriptor_fingerprint_value,
    )

    _write_cache(cache_path, payload_dict)
    return payload_dict


def _fingerprint_with_filters(descriptor_fp: str, request_filters: Mapping[str, Any]) -> str:
    if not request_filters:
        return descriptor_fp
    serialised = json.dumps(request_filters, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(f"{descriptor_fp}|{serialised}".encode("utf-8")).hexdigest()
    return digest


def _compile_filters(descriptor, request_filters: Optional[Mapping[str, Any]] = None) -> CompiledFilters:
    filters = CompiledFilters(
        response_types=set(),
        bet_types=set(),
        positions=set(),
        bucket_keys=set(),
        texture_keys=set(),
    )

    for step in descriptor.steps:
        qualifiers = {qual.lower() for qual in step.qualifiers}
        if step.street == "flop":
            if step.actor in {"responder", "villain", "population", "any"} and step.action in {"call", "raise"}:
                filters.response_types.add(step.action)
            if step.actor in {"bettor", "preflop_aggressor", "any"}:
                bet_type = BET_ACTION_TO_TYPE.get(step.action)
                if bet_type:
                    filters.bet_types.add(bet_type)
            if "in_position" in qualifiers:
                filters.positions.add("IP")
            if "out_of_position" in qualifiers:
                filters.positions.add("OOP")
            for qualifier in qualifiers:
                if qualifier.startswith("texture_"):
                    filters.texture_keys.add(qualifier.replace("texture_", ""))
        if step.street == "turn" and step.action in {"bet", "raise"}:
            if step.sizing and step.sizing.bucket_keys:
                filters.bucket_keys.update(step.sizing.bucket_keys)
            if step.sizing and step.sizing.ratio_min is not None:
                filters.ratio_min = (
                    max(filters.ratio_min, step.sizing.ratio_min)
                    if filters.ratio_min is not None
                    else step.sizing.ratio_min
                )
            if step.sizing and step.sizing.ratio_max is not None:
                filters.ratio_max = (
                    min(filters.ratio_max, step.sizing.ratio_max)
                    if filters.ratio_max is not None
                    else step.sizing.ratio_max
                )
            if "in_position" in qualifiers:
                filters.positions.add("IP")
            if "out_of_position" in qualifiers:
                filters.positions.add("OOP")
        if "heads_up" in qualifiers:
            filters.require_heads_up = True
        if "multiway" in qualifiers:
            filters.require_multiway = True

    if request_filters:
        exclude = request_filters.get("excludeHero")
        if exclude is None:
            exclude = request_filters.get("exclude_hero")
        if exclude is not None:
            filters.exclude_hero = bool(exclude)

    if not filters.response_types:
        filters.response_types = None
    if not filters.bet_types:
        filters.bet_types = None
    if not filters.positions:
        filters.positions = None
    if not filters.bucket_keys:
        filters.bucket_keys = None
    if not filters.texture_keys:
        filters.texture_keys = None

    return filters


def _matches_filters(event: Mapping[str, object], filters: CompiledFilters) -> bool:
    response_type = str(event.get("response_type") or "").lower()
    bet_type = str(event.get("bet_type") or "").lower()
    position = str(event.get("position") or "").upper()

    player_count_raw = event.get("player_count")
    try:
        player_count = int(player_count_raw)
    except (TypeError, ValueError):
        player_count = None

    bucket_key = event.get("turn_bucket_key")
    try:
        ratio_value = float(event.get("turn_ratio") or 0.0)
    except (TypeError, ValueError):
        ratio_value = 0.0

    if filters.response_types and response_type not in filters.response_types:
        return False
    if filters.bet_types and bet_type not in filters.bet_types:
        return False
    if filters.positions and position not in filters.positions:
        return False
    if filters.require_heads_up and player_count != 2:
        return False
    if filters.require_multiway and (player_count is None or player_count <= 2):
        return False
    if filters.bucket_keys and bucket_key not in filters.bucket_keys:
        return False
    if filters.ratio_min is not None and ratio_value < filters.ratio_min:
        return False
    if filters.ratio_max is not None and ratio_value > filters.ratio_max:
        return False
    if filters.exclude_hero:
        if bool(event.get("bettor_is_hero")) or bool(event.get("responder_is_hero")):
            return False
        if bool(event.get("hero_is_responder")):
            return False
    if filters.texture_keys:
        raw_textures = event.get("flop_texture_keys")
        texture_set: set[str]
        if isinstance(raw_textures, (list, tuple, set)):
            texture_set = {str(value).lower() for value in raw_textures}
        elif isinstance(raw_textures, str):
            texture_set = {raw_textures.lower()}
        else:
            texture_set = set()
        if not texture_set or texture_set.isdisjoint(filters.texture_keys):
            return False

    return True


def _build_payload(
    descriptor,
    stake_policy,
    filters,
    events,
    fingerprint,
    request_filters,
    descriptor_fp,
) -> dict:
    bucket_stats = {
        meta.key: {
            "events": 0,
            "fold": 0,
            "call": 0,
            "raise": 0,
            "ratio_sum": 0.0,
            "bet_sum": 0.0,
            "added_flop_sum": 0.0,
            "added_all_sum": 0.0,
            "share_all_sum": 0.0,
            "hand_categories": {key: 0 for key in HAND_TYPE_KEYS},
        }
        for meta in BUCKET_METADATA
    }

    context_counters = {
        "line_keys": Counter(),
        "bet_types": Counter(),
        "positions": Counter(),
        "player_counts": Counter(),
        "hero_positions": Counter(),
        "response_types": Counter(),
    }

    for event in events:
        bucket_key = event.get("turn_bucket_key")
        if bucket_key not in bucket_stats:
            continue

        stats = bucket_stats[bucket_key]
        stats["events"] += 1

        outcome = str(event.get("outcome") or "").lower()
        if outcome == "raise":
            stats["raise"] += 1
        elif outcome == "call":
            stats["call"] += 1
        else:
            stats["fold"] += 1

        try:
            ratio_value = float(event.get("turn_ratio") or 0.0)
        except (TypeError, ValueError):
            ratio_value = 0.0
        stats["ratio_sum"] += ratio_value

        try:
            bet_amount = float(event.get("bet_amount_bb") or 0.0)
        except (TypeError, ValueError):
            bet_amount = 0.0
        stats["bet_sum"] += bet_amount

        try:
            added_flop = float(event.get("total_added_flop_bb") or 0.0)
        except (TypeError, ValueError):
            added_flop = 0.0
        stats["added_flop_sum"] += added_flop

        try:
            added_all = float(event.get("total_added_all_bb") or 0.0)
        except (TypeError, ValueError):
            added_all = 0.0
        stats["added_all_sum"] += added_all

        try:
            share_all = float(event.get("total_share_all") or 0.0)
        except (TypeError, ValueError):
            share_all = 0.0
        stats["share_all_sum"] += share_all

        hand_primary = str(event.get("hand_primary") or "")
        if hand_primary in HAND_TYPE_SET:
            stats["hand_categories"][hand_primary] += 1
        if event.get("has_flush_draw"):
            stats["hand_categories"]["Flush Draw"] += 1
        if event.get("has_oesd_dg"):
            stats["hand_categories"]["OESD/DG"] += 1

        context_counters["line_keys"][str(event.get("line_key") or "")] += 1
        context_counters["bet_types"][str(event.get("bet_type") or "")] += 1
        context_counters["positions"][str(event.get("position") or "")] += 1
        context_counters["player_counts"][str(event.get("player_count") or "")] += 1
        context_counters["hero_positions"][str(event.get("hero_position") or "")] += 1
        context_counters["response_types"][str(event.get("response_type") or "")] += 1

    response_rows = []
    hand_rows = []
    total_events = sum(stats["events"] for stats in bucket_stats.values())

    for meta in BUCKET_METADATA:
        stats = bucket_stats[meta.key]
        events_count = stats["events"]
        fold_events = stats["fold"]
        call_events = stats["call"]
        raise_events = stats["raise"]
        continue_events = call_events + raise_events
        avg_ratio = stats["ratio_sum"] / events_count if events_count else 0.0
        avg_bet_bb = stats["bet_sum"] / events_count if events_count else 0.0
        avg_added_flop = stats["added_flop_sum"] / events_count if events_count else 0.0
        avg_added_all = stats["added_all_sum"] / events_count if events_count else 0.0
        avg_share_all = stats["share_all_sum"] / events_count if events_count else 0.0

        response_rows.append(
            {
                "bucket_key": meta.key,
                "bucket_label": meta.label,
                "events": events_count,
                "fold_events": fold_events,
                "call_events": call_events,
                "raise_events": raise_events,
                "continue_events": continue_events,
                "fold_pct": _percentage(fold_events, events_count),
                "call_pct": _percentage(call_events, events_count),
                "raise_pct": _percentage(raise_events, events_count),
                "continue_pct": _percentage(continue_events, events_count),
                "avg_ratio": avg_ratio,
                "avg_bet_bb": avg_bet_bb,
                "avg_added_flop_bb": avg_added_flop,
                "avg_added_all_bb": avg_added_all,
                "avg_share_all": avg_share_all,
            }
        )

        hand_rows.append(
            {
                "bucket_key": meta.key,
                "bucket_label": meta.label,
                "events": events_count,
                "categories": dict(stats["hand_categories"]),
            }
        )

    context = {
        "total_events": total_events,
        "applied_filters": _filters_metadata(filters),
        "distributions": {
            key: _counter_to_distribution(counter)
            for key, counter in context_counters.items()
            if counter
        },
    }

    return {
        "version": CURRENT_VERSION,
        "descriptor": descriptor.to_dict(),
        "stake_policy": {
            "token": stake_policy.cache_token(),
            "allowed": stake_policy.allowed_big_blinds,
        },
        "bucket_order": [{"key": meta.key, "label": meta.label} for meta in BUCKET_METADATA],
        "response_metrics": response_rows,
        "hand_metrics": hand_rows,
        "context": context,
        "fingerprint": fingerprint,
        "descriptor_fingerprint": descriptor_fp,
        "request_filters": request_filters,
        "using_sample": total_events == 0,
    }


def _percentage(part: int, total: int) -> float:
    if total <= 0 or part <= 0:
        return 0.0
    return (part / total) * 100.0


def _filters_metadata(filters: CompiledFilters) -> dict:
    data = {}
    if filters.response_types:
        data["response_types"] = sorted(filters.response_types)
    if filters.bet_types:
        data["bet_types"] = sorted(filters.bet_types)
    if filters.positions:
        data["positions"] = sorted(filters.positions)
    if filters.require_heads_up:
        data["heads_up"] = True
    if filters.require_multiway:
        data["multiway"] = True
    if filters.bucket_keys:
        data["bucket_keys"] = sorted(filters.bucket_keys)
    if filters.texture_keys:
        data["texture_keys"] = sorted(filters.texture_keys)
    if filters.ratio_min is not None or filters.ratio_max is not None:
        data["ratio_range"] = {
            "min": filters.ratio_min,
            "max": filters.ratio_max,
        }
    if filters.exclude_hero:
        data["exclude_hero"] = True
    return data


def _counter_to_distribution(counter: Counter) -> list[dict[str, object]]:
    return [
        {"key": key, "count": count}
        for key, count in counter.most_common()
        if key
    ]


def _resolve_cache_path(fingerprint: str, stake_policy: StakePolicy) -> Path:
    data_paths = build_data_paths()
    data_paths.ensure_cache_dir()
    filename = f"line_query_{stake_policy.cache_token()}_{fingerprint}.json"
    return data_paths.cache_dir / filename


def _read_cache(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != CURRENT_VERSION:
        return None
    return payload


def _write_cache(path: Path, payload: Mapping[str, object]) -> None:
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError:
        return


__all__ = ["CURRENT_VERSION", "query_line"]
