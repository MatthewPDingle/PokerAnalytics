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
from poker_analytics.services.flop_bucket_utils import BUCKET_KEYS, BUCKET_METADATA, bucket_keys_for_event
from poker_analytics.services.flop_response_matrix_builder import collect_line_events
from poker_analytics.services.line_descriptor import descriptor_fingerprint, parse_line_descriptor

CURRENT_VERSION = 8

UNKNOWN_HAND_KEY = "Unknown"
HAND_TYPE_KEYS: Sequence[str] = tuple(PRIMARY_HAND_TYPES) + tuple(DRAW_CATEGORIES) + (UNKNOWN_HAND_KEY,)
HAND_TYPE_SET = set(HAND_TYPE_KEYS)
RESPONDER_ACTION_ORDER: Sequence[str] = ("check", "bet", "call", "raise", "fold")
RESPONDER_ACTION_SET = set(RESPONDER_ACTION_ORDER)
BET_ACTION_TO_TYPE = {
    "cbet": "cbet",
    "donk": "donk",
    "stab": "stab",
    "lead": "stab",
    "probe": "stab",
}

REQUEST_BUCKET_EXPANSIONS: dict[str, set[str]] = {
    "pct_100_plus": {"pct_100_plus"},
    "pct_125_plus": {"pct_100_plus"},
}

BUCKET_KEY_SET = {meta.key for meta in BUCKET_METADATA}


def _event_bucket_keys(event: Mapping[str, object]) -> list[str]:
    payload = {
        "bucket_key": event.get("turn_bucket_key") or event.get("bucket_key"),
        "ratio": event.get("turn_ratio"),
        "is_check": event.get("is_check"),
        "is_all_in": event.get("is_all_in"),
        "is_one_bb": event.get("is_one_bb"),
    }
    return [key for key in bucket_keys_for_event(payload) if key in BUCKET_KEY_SET]


@dataclass
class CompiledFilters:
    response_types: Optional[set[str]] = None
    bet_types: Optional[set[str]] = None
    positions: Optional[set[str]] = None
    require_heads_up: bool = False
    require_multiway: bool = False
    bucket_keys: Optional[set[str]] = None
    preflop_bucket_keys: Optional[set[str]] = None
    ratio_min: Optional[float] = None
    ratio_max: Optional[float] = None
    exclude_hero: bool = False
    texture_keys: Optional[set[str]] = None
    players_dealt: Optional[set[int]] = None
    player_counts: Optional[set[int]] = None
    players_remaining: Optional[set[int]] = None
    hero_positions: Optional[set[str]] = None
    relative_positions: Optional[set[str]] = None
    line_keys: Optional[set[str]] = None
    min_preflop_raises: Optional[int] = None
    require_all_in_called: bool = False
    effective_stack_buckets: Optional[set[str]] = None
    spr_buckets: Optional[set[str]] = None


def query_line(
    payload: Mapping[str, object],
    *,
    events: Optional[Iterable[Mapping[str, object]]] = None,
    source: str | None = None,
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
    cache_path = _resolve_cache_path(cache_fingerprint, stake_policy, source=source)

    cached = _read_cache(cache_path)
    if cached is not None:
        return cached

    if events is not None:
        source_events = list(events)
    elif source is None:
        source_events = collect_line_events()
    else:
        # For non-default sources we rely on precomputed caches; without events
        # we fall back to an empty event set.
        source_events = []
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
        preflop_bucket_keys=set(),
        texture_keys=set(),
        players_dealt=set(),
        player_counts=set(),
        players_remaining=set(),
        hero_positions=set(),
        relative_positions=set(),
        line_keys=set(),
        effective_stack_buckets=set(),
        spr_buckets=set(),
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
        def _as_iterable(value):
            if isinstance(value, (list, tuple, set)):
                return value
            return [value]

        exclude = request_filters.get("excludeHero")
        if exclude is None:
            exclude = request_filters.get("exclude_hero")
        if exclude is not None:
            filters.exclude_hero = bool(exclude)

        bucket_keys = request_filters.get("bucket_keys") or request_filters.get("bucketKeys")
        if bucket_keys is not None:
            if isinstance(bucket_keys, (list, tuple, set)):
                incoming = {str(key) for key in bucket_keys}
            else:
                incoming = {str(bucket_keys)}

            expanded: set[str] = set()
            for key in incoming:
                expanded_keys = REQUEST_BUCKET_EXPANSIONS.get(key)
                if expanded_keys:
                    expanded.update(expanded_keys)
                else:
                    expanded.add(key)

            filters.bucket_keys = expanded or None

        preflop_bucket_keys = request_filters.get("preflop_bucket_keys") or request_filters.get("preflopBucketKeys")
        if preflop_bucket_keys is not None:
            if isinstance(preflop_bucket_keys, (list, tuple, set)):
                incoming = {str(key) for key in preflop_bucket_keys}
            else:
                incoming = {str(preflop_bucket_keys)}

            expanded: set[str] = set()
            for key in incoming:
                expanded_keys = REQUEST_BUCKET_EXPANSIONS.get(key)
                if expanded_keys:
                    expanded.update(expanded_keys)
                else:
                    expanded.add(key)

            filters.preflop_bucket_keys = expanded or None

        texture_keys = request_filters.get("texture_keys") or request_filters.get("textureKeys")
        if texture_keys is not None and filters.texture_keys is not None:
            for value in _as_iterable(texture_keys):
                text = str(value).strip().lower()
                if text:
                    filters.texture_keys.add(text)

        players_dealt_values = request_filters.get("players_dealt") or request_filters.get("playersDealt")
        if players_dealt_values is not None and filters.players_dealt is not None:
            for value in _as_iterable(players_dealt_values):
                try:
                    filters.players_dealt.add(int(value))
                except (TypeError, ValueError):
                    continue

        player_counts_values = request_filters.get("player_counts") or request_filters.get("playerCounts")
        if player_counts_values is not None and filters.player_counts is not None:
            for value in _as_iterable(player_counts_values):
                try:
                    filters.player_counts.add(int(value))
                except (TypeError, ValueError):
                    continue

        players_remaining_values = request_filters.get("players_remaining") or request_filters.get("playersRemaining")
        if players_remaining_values is not None and filters.players_remaining is not None:
            for value in _as_iterable(players_remaining_values):
                try:
                    filters.players_remaining.add(int(value))
                except (TypeError, ValueError):
                    continue

        hero_positions_values = request_filters.get("hero_positions") or request_filters.get("heroPositions")
        if hero_positions_values is not None and filters.hero_positions is not None:
            for value in _as_iterable(hero_positions_values):
                text = str(value).strip().upper()
                if text:
                    filters.hero_positions.add(text)

        relative_positions_values = request_filters.get("relative_positions") or request_filters.get("relativePositions")
        if relative_positions_values is not None and filters.relative_positions is not None:
            for value in _as_iterable(relative_positions_values):
                text = str(value).strip().lower()
                if text:
                    filters.relative_positions.add(text)

        eff_stack_values = request_filters.get("effective_stack_buckets") or request_filters.get("effectiveStackBuckets")
        if eff_stack_values is not None and filters.effective_stack_buckets is not None:
            for value in _as_iterable(eff_stack_values):
                text = str(value).strip()
                if text:
                    filters.effective_stack_buckets.add(text)

        spr_values = request_filters.get("spr_buckets") or request_filters.get("sprBuckets")
        if spr_values is not None and filters.spr_buckets is not None:
            for value in _as_iterable(spr_values):
                text = str(value).strip()
                if text:
                    filters.spr_buckets.add(text)

        ratio_min_value = request_filters.get("ratio_min")
        if ratio_min_value is None:
            ratio_min_value = request_filters.get("ratioMin")
        if ratio_min_value is not None:
            try:
                candidate = float(ratio_min_value)
            except (TypeError, ValueError):
                candidate = None
            if candidate is not None:
                filters.ratio_min = (
                    max(filters.ratio_min, candidate) if filters.ratio_min is not None else candidate
                )

        ratio_max_value = request_filters.get("ratio_max")
        if ratio_max_value is None:
            ratio_max_value = request_filters.get("ratioMax")
        if ratio_max_value is not None:
            try:
                candidate = float(ratio_max_value)
            except (TypeError, ValueError):
                candidate = None
            if candidate is not None:
                filters.ratio_max = (
                    min(filters.ratio_max, candidate) if filters.ratio_max is not None else candidate
                )

        min_raises_value = request_filters.get("min_preflop_raises")
        if min_raises_value is None:
            min_raises_value = request_filters.get("minPreflopRaises")
        if min_raises_value is not None:
            try:
                candidate = int(min_raises_value)
            except (TypeError, ValueError):
                candidate = None
            if candidate is not None:
                filters.min_preflop_raises = (
                    max(filters.min_preflop_raises, candidate)
                    if filters.min_preflop_raises is not None
                    else candidate
                )

        all_in_called_value = request_filters.get("all_in_called")
        if all_in_called_value is None:
            all_in_called_value = request_filters.get("allInCalled")
        if all_in_called_value is not None:
            filters.require_all_in_called = bool(all_in_called_value)

        line_keys_values = request_filters.get("line_keys") or request_filters.get("lineKeys")
        if line_keys_values is not None and filters.line_keys is not None:
            for value in _as_iterable(line_keys_values):
                text = str(value).strip().lower()
                if text:
                    filters.line_keys.add(text)

    if not filters.response_types:
        filters.response_types = None
    if not filters.bet_types:
        filters.bet_types = None
    if not filters.positions:
        filters.positions = None
    if not filters.bucket_keys:
        filters.bucket_keys = None
    if not filters.preflop_bucket_keys:
        filters.preflop_bucket_keys = None
    if not filters.texture_keys:
        filters.texture_keys = None
    if not filters.players_dealt:
        filters.players_dealt = None
    if not filters.player_counts:
        filters.player_counts = None
    if not filters.players_remaining:
        filters.players_remaining = None
    if not filters.hero_positions:
        filters.hero_positions = None
    if not filters.relative_positions:
        filters.relative_positions = None
    if not filters.line_keys:
        filters.line_keys = None
    if not filters.effective_stack_buckets:
        filters.effective_stack_buckets = None
    if not filters.spr_buckets:
        filters.spr_buckets = None

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

    bucket_keys = _event_bucket_keys(event)
    preflop_bucket = str(event.get("preflop_bucket_key") or "")
    try:
        ratio_value = float(event.get("turn_ratio") or 0.0)
    except (TypeError, ValueError):
        ratio_value = 0.0

    players_dealt_raw = event.get("players_dealt")
    try:
        players_dealt = int(players_dealt_raw)
    except (TypeError, ValueError):
        players_dealt = None

    players_remaining_raw = event.get("players_remaining")
    try:
        players_remaining = int(players_remaining_raw)
    except (TypeError, ValueError):
        players_remaining = None

    hero_position = str(event.get("hero_position") or "").upper()
    relative_position = str(event.get("relative_position") or "").lower()
    line_key = str(event.get("line_key") or "").lower()
    effective_stack_bucket = str(event.get("effective_stack_bucket") or "")
    spr_bucket = str(event.get("spr_bucket") or "")

    try:
        preflop_aggression = int(event.get("preflop_aggression_level") or 0)
    except (TypeError, ValueError):
        preflop_aggression = 0

    all_in_called = bool(event.get("all_in_called"))

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
    if filters.player_counts and (player_count is None or player_count not in filters.player_counts):
        return False
    if filters.bucket_keys and (not bucket_keys or filters.bucket_keys.isdisjoint(bucket_keys)):
        return False
    if filters.preflop_bucket_keys and (not preflop_bucket or preflop_bucket not in filters.preflop_bucket_keys):
        return False
    if filters.ratio_min is not None and ratio_value < filters.ratio_min:
        return False
    if filters.ratio_max is not None and ratio_value > filters.ratio_max:
        return False
    if filters.players_dealt and (players_dealt is None or players_dealt not in filters.players_dealt):
        return False
    if filters.players_remaining and (players_remaining is None or players_remaining not in filters.players_remaining):
        return False
    if filters.hero_positions and hero_position not in filters.hero_positions:
        return False
    if filters.relative_positions and relative_position not in filters.relative_positions:
        return False
    if filters.effective_stack_buckets and effective_stack_bucket not in filters.effective_stack_buckets:
        return False
    if filters.spr_buckets and spr_bucket not in filters.spr_buckets:
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
    if filters.line_keys and (not line_key or line_key not in filters.line_keys):
        return False
    if filters.min_preflop_raises is not None and preflop_aggression < filters.min_preflop_raises:
        return False
    if filters.require_all_in_called and not all_in_called:
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
    bucket_stats = {meta.key: _create_action_aggregate(meta) for meta in BUCKET_METADATA}
    totals_stats = _create_action_aggregate(None)

    context_counters = {
        "line_keys": Counter(),
        "bet_types": Counter(),
        "positions": Counter(),
        "player_counts": Counter(),
        "players_dealt": Counter(),
        "players_remaining": Counter(),
        "hero_positions": Counter(),
        "relative_positions": Counter(),
        "actor_seats": Counter(),
        "all_in_called": Counter(),
        "effective_stack_buckets": Counter(),
        "spr_buckets": Counter(),
        "response_types": Counter(),
        "responder_seats": Counter(),
        "responder_actions": Counter(),
        "preflop_buckets": Counter(),
    }

    total_events = 0

    for event in events:
        bucket_keys = _event_bucket_keys(event)
        if not bucket_keys:
            continue

        outcome = str(event.get("outcome") or "").lower()
        base_bucket_key = str(event.get("bucket_key") or "")
        preflop_bucket = str(event.get("preflop_bucket_key") or "")

        try:
            ratio_value = float(event.get("turn_ratio") or 0.0)
        except (TypeError, ValueError):
            ratio_value = 0.0

        try:
            bet_amount = float(event.get("bet_amount_bb") or 0.0)
        except (TypeError, ValueError):
            bet_amount = 0.0

        try:
            added_flop = float(event.get("total_added_flop_bb") or 0.0)
        except (TypeError, ValueError):
            added_flop = 0.0

        try:
            added_all = float(event.get("total_added_all_bb") or 0.0)
        except (TypeError, ValueError):
            added_all = 0.0

        try:
            share_all = float(event.get("total_share_all") or 0.0)
        except (TypeError, ValueError):
            share_all = 0.0

        hand_primary = str(event.get("hand_primary") or "")
        has_flush_draw = bool(event.get("has_flush_draw"))
        has_oesd_dg = bool(event.get("has_oesd_dg"))

        raw_responses = event.get("behind_responses")
        behind_responses: list[Mapping[str, object]] = []
        if isinstance(raw_responses, list):
            behind_responses = [response for response in raw_responses if isinstance(response, Mapping)]

        for bucket_key in bucket_keys:
            stats = bucket_stats.get(bucket_key)
            if stats is None:
                continue
            _accumulate_action(
                stats,
                bucket_key=bucket_key,
                outcome=outcome,
                ratio_value=ratio_value,
                bet_amount=bet_amount,
                added_flop=added_flop,
                added_all=added_all,
                share_all=share_all,
                hand_primary=hand_primary,
                has_flush_draw=has_flush_draw,
                has_oesd_dg=has_oesd_dg,
                behind_responses=behind_responses,
            )

        primary_bucket = base_bucket_key or bucket_keys[0]
        _accumulate_action(
            totals_stats,
            bucket_key=primary_bucket,
            outcome=outcome,
            ratio_value=ratio_value,
            bet_amount=bet_amount,
            added_flop=added_flop,
            added_all=added_all,
            share_all=share_all,
            hand_primary=hand_primary,
            has_flush_draw=has_flush_draw,
            has_oesd_dg=has_oesd_dg,
            behind_responses=behind_responses,
        )

        total_events += 1

        actor_seat = str(event.get("actor_seat") or "")
        if actor_seat:
            context_counters["actor_seats"][actor_seat] += 1

        context_counters["line_keys"][str(event.get("line_key") or "")] += 1
        context_counters["bet_types"][str(event.get("bet_type") or "")] += 1
        context_counters["positions"][str(event.get("position") or "")] += 1
        context_counters["player_counts"][str(event.get("player_count") or "")] += 1
        context_counters["players_dealt"][str(event.get("players_dealt") or "")] += 1
        context_counters["players_remaining"][str(event.get("players_remaining") or "")] += 1
        context_counters["hero_positions"][str(event.get("hero_position") or "")] += 1
        context_counters["relative_positions"][str(event.get("relative_position") or "")] += 1
        context_counters["all_in_called"]["yes" if event.get("all_in_called") else "no"] += 1

        eff_bucket_key = str(event.get("effective_stack_bucket") or "")
        if eff_bucket_key:
            context_counters["effective_stack_buckets"][eff_bucket_key] += 1
        spr_bucket_key = str(event.get("spr_bucket") or "")
        if spr_bucket_key:
            context_counters["spr_buckets"][spr_bucket_key] += 1

        response_type = str(event.get("response_type") or "")
        if response_type:
            context_counters["response_types"][response_type] += 1

        for response in behind_responses:
            seat_label = str(response.get("seat_label") or "")
            if seat_label:
                context_counters["responder_seats"][seat_label] += 1
            resp_action = str(response.get("response_type") or "")
            if resp_action:
                context_counters["responder_actions"][resp_action] += 1

        if preflop_bucket:
            context_counters["preflop_buckets"][preflop_bucket] += 1

    action_rows = [
        _finalise_action_summary(meta, bucket_stats[meta.key])
        for meta in BUCKET_METADATA
    ]
    totals_row = _finalise_action_summary(None, totals_stats, action_key="all", action_label="All Actions")

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
        "action_summaries": action_rows,
        "totals": totals_row,
        "context": context,
        "fingerprint": fingerprint,
        "descriptor_fingerprint": descriptor_fp,
        "request_filters": request_filters,
        "using_sample": total_events == 0,
    }


def _create_action_aggregate(_: Optional[object]) -> dict[str, object]:
    return {
        "events": 0,
        "fold_events": 0,
        "call_events": 0,
        "raise_events": 0,
        "ratio_sum": 0.0,
        "bet_sum": 0.0,
        "added_flop_sum": 0.0,
        "added_all_sum": 0.0,
        "share_all_sum": 0.0,
        "hand_categories": Counter(),
        "responder": _create_responder_aggregate(),
        "hero_action_counts": Counter(),
    }


def _create_responder_aggregate() -> dict[str, object]:
    return {
        "total": 0,
        "action_counts": Counter(),
        "hand_categories": Counter(),
        "bucket_counts": Counter(),
        "seats": {},
    }


def _create_responder_seat_summary(seat_label: str) -> dict[str, object]:
    return {
        "seat_label": seat_label,
        "responses": 0,
        "action_counts": Counter(),
        "hand_categories": Counter(),
        "bucket_counts": Counter(),
        "relative_positions": Counter(),
    }


def _increment_hand_category(counter: Counter, primary: str, *, known: bool) -> None:
    if known and primary:
        key = primary if primary in HAND_TYPE_SET else UNKNOWN_HAND_KEY
        counter[key] += 1
    else:
        counter[UNKNOWN_HAND_KEY] += 1


def _accumulate_action(
    summary: dict[str, object],
    *,
    bucket_key: str,
    outcome: str,
    ratio_value: float,
    bet_amount: float,
    added_flop: float,
    added_all: float,
    share_all: float,
    hand_primary: str,
    has_flush_draw: bool,
    has_oesd_dg: bool,
    behind_responses: Sequence[Mapping[str, object]],
) -> None:
    summary["events"] += 1

    if bucket_key != "check":
        if outcome == "raise":
            summary["raise_events"] += 1
        elif outcome == "call":
            summary["call_events"] += 1
        elif outcome == "fold":
            summary["fold_events"] += 1
        summary["ratio_sum"] += ratio_value
        summary["bet_sum"] += bet_amount

    summary["added_flop_sum"] += added_flop
    summary["added_all_sum"] += added_all
    summary["share_all_sum"] += share_all

    _increment_hand_category(summary["hand_categories"], hand_primary, known=bool(hand_primary))
    if has_flush_draw:
        summary["hand_categories"]["Flush Draw"] += 1
    if has_oesd_dg:
        summary["hand_categories"]["OESD/DG"] += 1

    if behind_responses:
        _accumulate_responder(summary["responder"], behind_responses)

    hero_actions: Counter = summary["hero_action_counts"]  # type: ignore[assignment]
    hero_actions[bucket_key] += 1
    if bucket_key == "check":
        hero_actions["check"] += 1
    else:
        hero_actions["bet"] += 1
        hero_actions["bet_any"] += 1
        if bucket_key == "all_in":
            hero_actions["all_in"] += 1
        if bucket_key == "one_bb":
            hero_actions["one_bb"] += 1


def _accumulate_responder(summary: dict[str, object], responses: Sequence[Mapping[str, object]]) -> None:
    seats: dict[str, dict[str, object]] = summary["seats"]  # type: ignore[assignment]
    for response in responses:
        response_type = str(response.get("response_type") or "").lower()
        if response_type not in RESPONDER_ACTION_SET:
            continue

        summary["total"] += 1
        summary["action_counts"][response_type] += 1

        bucket_keys = response.get("bucket_keys")
        if isinstance(bucket_keys, (list, tuple, set)):
            for key in bucket_keys:
                if key:
                    summary["bucket_counts"][key] += 1

        seat_label = str(response.get("seat_label") or "UNKNOWN")
        seat_summary = seats.get(seat_label)
        if seat_summary is None:
            seat_summary = _create_responder_seat_summary(seat_label)
            seats[seat_label] = seat_summary
        seat_summary["responses"] += 1
        seat_summary["action_counts"][response_type] += 1
        if isinstance(bucket_keys, (list, tuple, set)):
            for key in bucket_keys:
                if key:
                    seat_summary["bucket_counts"][key] += 1

        relative_position = str(response.get("relative_position") or "unknown")
        seat_summary["relative_positions"][relative_position] += 1

        known = bool(response.get("hole_cards_known"))
        hand_primary = str(response.get("hand_primary") or "")
        _increment_hand_category(summary["hand_categories"], hand_primary, known=known)
        _increment_hand_category(seat_summary["hand_categories"], hand_primary, known=known)

        if response.get("has_flush_draw"):
            summary["hand_categories"]["Flush Draw"] += 1
            seat_summary["hand_categories"]["Flush Draw"] += 1
        if response.get("has_oesd_dg"):
            summary["hand_categories"]["OESD/DG"] += 1
            seat_summary["hand_categories"]["OESD/DG"] += 1


def _finalise_action_summary(
    meta: Optional[object],
    stats: dict[str, object],
    *,
    action_key: Optional[str] = None,
    action_label: Optional[str] = None,
) -> dict[str, object]:
    key = action_key if action_key is not None else (getattr(meta, "key", None) if meta else None)
    label = action_label if action_label is not None else (getattr(meta, "label", None) if meta else None)

    events = stats["events"]
    fold_events = stats["fold_events"]
    call_events = stats["call_events"]
    raise_events = stats["raise_events"]
    continue_events = call_events + raise_events

    avg_ratio = stats["ratio_sum"] / events if events else 0.0
    avg_bet = stats["bet_sum"] / events if events else 0.0
    avg_added_flop = stats["added_flop_sum"] / events if events else 0.0
    avg_added_all = stats["added_all_sum"] / events if events else 0.0
    avg_share_all = stats["share_all_sum"] / events if events else 0.0

    return {
        "action_key": key,
        "action_label": label,
        "events": events,
        "fold_events": fold_events,
        "call_events": call_events,
        "raise_events": raise_events,
        "continue_events": continue_events,
        "fold_pct": _percentage(fold_events, events),
        "call_pct": _percentage(call_events, events),
        "raise_pct": _percentage(raise_events, events),
        "continue_pct": _percentage(continue_events, events),
        "avg_ratio": avg_ratio,
        "avg_bet_bb": avg_bet,
        "avg_added_flop_bb": avg_added_flop,
        "avg_added_all_bb": avg_added_all,
        "avg_share_all": avg_share_all,
        "hand_categories": _finalise_hand_categories(stats["hand_categories"]),
        "responder_summary": _finalise_responder_summary(stats["responder"]),
        "hero_actions": _finalise_hero_actions(stats["hero_action_counts"]),
    }


def _finalise_responder_summary(summary: dict[str, object]) -> dict[str, object]:
    seats: dict[str, dict[str, object]] = summary["seats"]  # type: ignore[assignment]
    seat_rows = []
    for seat_label in sorted(seats.keys()):
        seat_data = seats[seat_label]
        seat_rows.append(
            {
                "seat_label": seat_label,
                "responses": seat_data["responses"],
                "action_counts": _finalise_action_counts(seat_data["action_counts"]),
                "hand_categories": _finalise_hand_categories(seat_data["hand_categories"]),
                "bet_bucket_counts": _finalise_bucket_counts(seat_data["bucket_counts"]),
                "relative_positions": {key: int(value) for key, value in seat_data["relative_positions"].items()},
            }
        )

    return {
        "total_responses": summary["total"],
        "action_counts": _finalise_action_counts(summary["action_counts"]),
        "hand_categories": _finalise_hand_categories(summary["hand_categories"]),
        "bet_bucket_counts": _finalise_bucket_counts(summary["bucket_counts"]),
        "seats": seat_rows,
    }


def _finalise_hand_categories(counter: Counter) -> dict[str, int]:
    return {key: int(counter.get(key, 0)) for key in HAND_TYPE_KEYS}


def _finalise_action_counts(counter: Counter) -> dict[str, int]:
    return {action: int(counter.get(action, 0)) for action in RESPONDER_ACTION_ORDER}


def _finalise_hero_actions(counter: Counter) -> dict[str, int]:
    return {key: int(value) for key, value in counter.items()}


def _finalise_bucket_counts(counter: Counter) -> dict[str, int]:
    return {key: int(counter[key]) for key in BUCKET_KEYS if counter.get(key)}


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
    if filters.preflop_bucket_keys:
        data["preflop_bucket_keys"] = sorted(filters.preflop_bucket_keys)
    if filters.texture_keys:
        data["texture_keys"] = sorted(filters.texture_keys)
    if filters.players_dealt:
        data["players_dealt"] = sorted(filters.players_dealt)
    if filters.player_counts:
        data["player_counts"] = sorted(filters.player_counts)
    if filters.players_remaining:
        data["players_remaining"] = sorted(filters.players_remaining)
    if filters.hero_positions:
        data["hero_positions"] = sorted(filters.hero_positions)
    if filters.relative_positions:
        data["relative_positions"] = sorted(filters.relative_positions)
    if filters.effective_stack_buckets:
        data["effective_stack_buckets"] = sorted(filters.effective_stack_buckets)
    if filters.spr_buckets:
        data["spr_buckets"] = sorted(filters.spr_buckets)
    if filters.ratio_min is not None or filters.ratio_max is not None:
        data["ratio_range"] = {
            "min": filters.ratio_min,
            "max": filters.ratio_max,
        }
    if filters.line_keys:
        data["line_keys"] = sorted(filters.line_keys)
    if filters.min_preflop_raises is not None:
        data["min_preflop_raises"] = filters.min_preflop_raises
    if filters.exclude_hero:
        data["exclude_hero"] = True
    if filters.require_all_in_called:
        data["all_in_called"] = True
    return data


def _counter_to_distribution(counter: Counter) -> list[dict[str, object]]:
    return [
        {"key": key, "count": count}
        for key, count in counter.most_common()
        if key
    ]


def _resolve_cache_path(fingerprint: str, stake_policy: StakePolicy, *, source: str | None = None) -> Path:
    data_paths = build_data_paths()
    data_paths.ensure_cache_dir()
    base_dir = data_paths.cache_dir
    if source:
        base_dir = base_dir / source
        base_dir.mkdir(parents=True, exist_ok=True)
    filename = f"line_query_{stake_policy.cache_token()}_{fingerprint}.json"
    return base_dir / filename


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
