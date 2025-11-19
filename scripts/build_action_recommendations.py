#!/usr/bin/env python3
"""Build action quick-reference recommendations from response matrices.

This script aggregates the flop / turn / river response-matrix caches into
``action_recommendations_<stake>.json`` payloads under ``var/cache/<source>/``.

The Action Quick Reference page then reads these precomputed rows via the
``/api/action-reference`` endpoint.

Usage (from the repo root, with the virtualenv activated):

    python scripts/build_action_recommendations.py --source drivehud
    python scripts/build_action_recommendations.py --source pokerstars_nl10

If ``--source`` is omitted or set to ``drivehud``, the script uses the default
DriveHUD / Ignition response-matrix caches rooted at ``var/cache/``. For other
sources (e.g. ``pokerstars_nl10``) the script reads the per-source caches from
``var/cache/<source>/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(SRC_ROOT), str(REPO_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from poker_analytics.config import build_data_paths  # noqa: E402
from poker_analytics.data.stakes import StakePolicy  # noqa: E402
from poker_analytics.services.flop_response_matrix import (  # noqa: E402
    load_flop_response_matrix,
)
from poker_analytics.services.turn_response_matrix import (  # noqa: E402
    load_turn_response_matrix,
)
from poker_analytics.services.river_response_matrix import (  # noqa: E402
    load_river_response_matrix,
)


MIN_EVENTS = 50
MIN_FOLD_SURPLUS = 5.0


@dataclass
class BucketAggregate:
    events: int = 0
    fold_events: int = 0
    call_events: int = 0
    raise_events: int = 0
    ratio_sum: float = 0.0
    share_sum: float = 0.0
    breakeven_sum: float = 0.0


@dataclass
class BucketSummary:
    events: int
    fold_pct: float
    call_pct: float
    raise_pct: float
    continue_pct: float
    avg_ratio: float
    avg_share_all: float
    avg_breakeven_pct: float
    fold_surplus: float


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _summarise_bucket(agg: BucketAggregate) -> BucketSummary:
    events = agg.events
    if events <= 0:
        return BucketSummary(
            events=0,
            fold_pct=0.0,
            call_pct=0.0,
            raise_pct=0.0,
            continue_pct=0.0,
            avg_ratio=0.0,
            avg_share_all=0.0,
            avg_breakeven_pct=0.0,
            fold_surplus=0.0,
        )

    fold_pct = 100.0 * agg.fold_events / events
    call_pct = 100.0 * agg.call_events / events
    raise_pct = 100.0 * agg.raise_events / events
    continue_pct = call_pct + raise_pct
    avg_ratio = agg.ratio_sum / events
    avg_share_all = agg.share_sum / events
    avg_breakeven_pct = agg.breakeven_sum / events
    fold_surplus = fold_pct - avg_breakeven_pct

    return BucketSummary(
        events=events,
        fold_pct=fold_pct,
        call_pct=call_pct,
        raise_pct=raise_pct,
        continue_pct=continue_pct,
        avg_ratio=avg_ratio,
        avg_share_all=avg_share_all,
        avg_breakeven_pct=avg_breakeven_pct,
        fold_surplus=fold_surplus,
    )


def _format_fold_surplus(value: float) -> str:
    if value >= 0:
        return f"+{value:.1f}"
    return f"{value:.1f}"


def _build_flop_recommendations(payload: Mapping[str, object]) -> List[Dict[str, object]]:
    """Derive bluff + value recommendations from the flop response matrix."""

    bucket_order = payload.get("bucket_order") or []
    bucket_labels = {
        entry["key"]: entry["label"] for entry in bucket_order if isinstance(entry, Mapping)
    }

    bet_types = payload.get("bet_types") or []
    bet_type_labels = {
        entry["key"]: entry["label"] for entry in bet_types if isinstance(entry, Mapping)
    }

    textures = payload.get("textures") or []
    texture_labels = {
        entry["key"]: entry["label"] for entry in textures if isinstance(entry, Mapping)
    }

    preflop_categories = payload.get("preflop_categories") or []
    preflop_labels = {
        entry["key"]: entry["label"] for entry in preflop_categories if isinstance(entry, Mapping)
    }

    spr_buckets = payload.get("spr_buckets") or []
    spr_labels = {
        entry["key"]: entry["label"] for entry in spr_buckets if isinstance(entry, Mapping)
    }

    scenarios = payload.get("scenarios") or []

    # Combination key:
    # (street, preflop_action, bet_classification, texture_label, players, bettor_position, spr_bucket_label)
    combo_aggregates: MutableMapping[
        Tuple[str, str, str, str, str, str, str],
        MutableMapping[str, BucketAggregate],
    ] = defaultdict(dict)

    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            continue

        bet_type = scenario.get("bet_type")
        position = scenario.get("position")
        player_count = scenario.get("player_count")
        texture_key = scenario.get("texture_key") or "any"
        preflop_key = scenario.get("preflop_key") or "any"
        spr_bucket_key = scenario.get("spr_bucket") or "any"

        bet_label = bet_type_labels.get(bet_type)
        texture_label = texture_labels.get(texture_key)
        preflop_label = preflop_labels.get(preflop_key)
        spr_label = "All SPRs" if spr_bucket_key == "any" else spr_labels.get(spr_bucket_key)

        if bet_label is None or texture_label is None or preflop_label is None or spr_label is None:
            continue

        # Bettor position choices: Any + specific (IP/OOP)
        position_labels = ["Any"]
        if isinstance(position, str) and position:
            position_labels.append(position)

        # Player count choices: Any + specific count
        players_labels = ["Any"]
        try:
            numeric_players = int(player_count)
            if numeric_players > 0:
                players_labels.append(str(numeric_players))
        except (TypeError, ValueError):
            pass

        # Bet classifications: All Bet Types + specific bet type label
        bet_classifications = ["All Bet Types", bet_label]

        metrics = scenario.get("metrics") or []

        for bet_classification in bet_classifications:
            for players_label in players_labels:
                for position_label in position_labels:
                    combo_key = (
                        "Flop",
                        preflop_label,
                        bet_classification,
                        texture_label,
                        players_label,
                        position_label,
                        spr_label,
                    )
                    bucket_map = combo_aggregates[combo_key]

                    for metric in metrics:
                        if not isinstance(metric, Mapping):
                            continue
                        bucket_key = metric.get("bucket_key")
                        if not isinstance(bucket_key, str):
                            continue
                        if bucket_key == "check":
                            continue

                        events = int(metric.get("events") or 0)
                        if events <= 0:
                            continue

                        aggregate = bucket_map.get(bucket_key)
                        if aggregate is None:
                            aggregate = BucketAggregate()
                            bucket_map[bucket_key] = aggregate

                        aggregate.events += events
                        aggregate.fold_events += int(metric.get("fold_events") or 0)
                        aggregate.call_events += int(metric.get("call_events") or 0)
                        aggregate.raise_events += int(metric.get("raise_events") or 0)
                        aggregate.ratio_sum += _safe_float(metric.get("avg_ratio")) * events
                        aggregate.share_sum += _safe_float(metric.get("avg_share_all")) * events
                        aggregate.breakeven_sum += _safe_float(metric.get("avg_breakeven_pct")) * events

    rows: List[Dict[str, object]] = []

    for (
        street,
        preflop_action,
        bet_classification,
        texture_label,
        players_label,
        bettor_position,
        spr_bucket_label,
    ), bucket_map in combo_aggregates.items():
        summaries: Dict[str, BucketSummary] = {
            bucket_key: _summarise_bucket(aggregate)
            for bucket_key, aggregate in bucket_map.items()
        }

        # Bluff recommendations: rank by fold surplus.
        bluff_candidates: List[Tuple[str, str, BucketSummary]] = []
        for bucket_key, summary in summaries.items():
            if summary.events < MIN_EVENTS:
                continue
            if summary.fold_surplus < MIN_FOLD_SURPLUS:
                continue
            label = bucket_labels.get(bucket_key)
            if not label:
                continue
            bluff_candidates.append((bucket_key, label, summary))

        bluff_candidates.sort(
            key=lambda item: (-item[2].fold_surplus, -item[2].events),
        )

        for rank, (_, bucket_label, summary) in enumerate(bluff_candidates):
            action_text = (
                f"Bet {bucket_label} — folds {summary.fold_pct:.1f}% "
                f"(calls {summary.call_pct:.1f}%, raises {summary.raise_pct:.1f}%), "
                f"adds {summary.avg_share_all:.2f}× pot vs {summary.avg_breakeven_pct:.1f}% breakeven, "
                f"fold surplus {_format_fold_surplus(summary.fold_surplus)}pp, "
                f"n={summary.events}"
            )

            rows.append(
                {
                    "street": street,
                    "preflop_action": preflop_action,
                    "bet_classification": bet_classification,
                    "flop_texture": texture_label,
                    "players": players_label,
                    "bettor_position": bettor_position,
                    "spr_bucket": spr_bucket_label,
                    "situation": "Bluff",
                    "action": action_text,
                    "rank": rank,
                    "avg_bet_pct": summary.avg_ratio * 100.0,
                }
            )

        # Value recommendations: rank by average pot share added.
        value_candidates: List[Tuple[str, str, BucketSummary]] = []
        for bucket_key, summary in summaries.items():
            if summary.events < MIN_EVENTS:
                continue
            if summary.avg_share_all <= 0:
                continue
            label = bucket_labels.get(bucket_key)
            if not label:
                continue
            value_candidates.append((bucket_key, label, summary))

        value_candidates.sort(
            key=lambda item: (-item[2].avg_share_all, -item[2].events),
        )

        for rank, (_, bucket_label, summary) in enumerate(value_candidates[:2]):
            action_text = (
                f"Bet {bucket_label} — adds {summary.avg_share_all:.2f}× pot, "
                f"villain continues {summary.continue_pct:.1f}% "
                f"(calls {summary.call_pct:.1f}%, raises {summary.raise_pct:.1f}%), "
                f"fold surplus {_format_fold_surplus(summary.fold_surplus)}pp, "
                f"n={summary.events}"
            )

            rows.append(
                {
                    "street": street,
                    "preflop_action": preflop_action,
                    "bet_classification": bet_classification,
                    "flop_texture": texture_label,
                    "players": players_label,
                    "bettor_position": bettor_position,
                    "spr_bucket": spr_bucket_label,
                    "situation": "Value",
                    "action": action_text,
                    "rank": rank,
                    "avg_bet_pct": summary.avg_ratio * 100.0,
                }
            )

    return rows


def _build_turn_or_river_recommendations(
    payload: Mapping[str, object],
    street: str,
) -> List[Dict[str, object]]:
    """Derive bluff + value recommendations from turn/river response matrices."""

    bucket_order = payload.get("bucket_order") or []
    bucket_labels = {
        entry["key"]: entry["label"] for entry in bucket_order if isinstance(entry, Mapping)
    }

    betting_lines = payload.get("betting_lines") or []
    line_labels = {
        entry["key"]: entry["label"] for entry in betting_lines if isinstance(entry, Mapping)
    }

    textures = payload.get("textures") or []
    texture_labels = {
        entry["key"]: entry["label"] for entry in textures if isinstance(entry, Mapping)
    }

    preflop_categories = payload.get("preflop_categories") or []
    preflop_labels = {
        entry["key"]: entry["label"] for entry in preflop_categories if isinstance(entry, Mapping)
    }

    spr_buckets = payload.get("spr_buckets") or []
    spr_labels = {
        entry["key"]: entry["label"] for entry in spr_buckets if isinstance(entry, Mapping)
    }

    scenarios = payload.get("scenarios") or []

    combo_aggregates: MutableMapping[
        Tuple[str, str, str, str, str, str, str],
        MutableMapping[str, BucketAggregate],
    ] = defaultdict(dict)

    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            continue

        bet_line = scenario.get("bet_line")
        position = scenario.get("position")
        player_count = scenario.get("player_count")
        texture_key = scenario.get("texture_key") or "any"
        preflop_key = scenario.get("preflop_key") or "any"
        spr_bucket_key = scenario.get("spr_bucket") or "any"

        bet_label = line_labels.get(bet_line)
        texture_label = texture_labels.get(texture_key)
        preflop_label = preflop_labels.get(preflop_key)
        spr_label = "All SPRs" if spr_bucket_key == "any" else spr_labels.get(spr_bucket_key)

        if bet_label is None or texture_label is None or preflop_label is None or spr_label is None:
            continue

        position_labels = ["Any"]
        if isinstance(position, str) and position:
            position_labels.append(position)

        players_labels = ["Any"]
        try:
            numeric_players = int(player_count)
            if numeric_players > 0:
                players_labels.append(str(numeric_players))
        except (TypeError, ValueError):
            pass

        bet_classifications = ["All Bet Types", bet_label]

        metrics = scenario.get("metrics") or []

        for bet_classification in bet_classifications:
            for players_label in players_labels:
                for position_label in position_labels:
                    combo_key = (
                        street,
                        preflop_label,
                        bet_classification,
                        texture_label,
                        players_label,
                        position_label,
                        spr_label,
                    )
                    bucket_map = combo_aggregates[combo_key]

                    for metric in metrics:
                        if not isinstance(metric, Mapping):
                            continue
                        bucket_key = metric.get("bucket_key")
                        if not isinstance(bucket_key, str):
                            continue
                        if bucket_key == "check":
                            continue

                        events = int(metric.get("events") or 0)
                        if events <= 0:
                            continue

                        aggregate = bucket_map.get(bucket_key)
                        if aggregate is None:
                            aggregate = BucketAggregate()
                            bucket_map[bucket_key] = aggregate

                        aggregate.events += events
                        aggregate.fold_events += int(metric.get("fold_events") or 0)
                        aggregate.call_events += int(metric.get("call_events") or 0)
                        aggregate.raise_events += int(metric.get("raise_events") or 0)
                        aggregate.ratio_sum += _safe_float(metric.get("avg_ratio")) * events
                        aggregate.share_sum += _safe_float(metric.get("avg_share_all")) * events
                        aggregate.breakeven_sum += _safe_float(metric.get("avg_breakeven_pct")) * events

    rows: List[Dict[str, object]] = []

    for (
        street_label,
        preflop_action,
        bet_classification,
        texture_label,
        players_label,
        bettor_position,
        spr_bucket_label,
    ), bucket_map in combo_aggregates.items():
        summaries: Dict[str, BucketSummary] = {
            bucket_key: _summarise_bucket(aggregate)
            for bucket_key, aggregate in bucket_map.items()
        }

        bluff_candidates: List[Tuple[str, str, BucketSummary]] = []
        for bucket_key, summary in summaries.items():
            if summary.events < MIN_EVENTS:
                continue
            if summary.fold_surplus < MIN_FOLD_SURPLUS:
                continue
            label = bucket_labels.get(bucket_key)
            if not label:
                continue
            bluff_candidates.append((bucket_key, label, summary))

        bluff_candidates.sort(
            key=lambda item: (-item[2].fold_surplus, -item[2].events),
        )

        for rank, (_, bucket_label, summary) in enumerate(bluff_candidates):
            action_text = (
                f"Bet {bucket_label} — folds {summary.fold_pct:.1f}% "
                f"(calls {summary.call_pct:.1f}%, raises {summary.raise_pct:.1f}%), "
                f"adds {summary.avg_share_all:.2f}× pot vs {summary.avg_breakeven_pct:.1f}% breakeven, "
                f"fold surplus {_format_fold_surplus(summary.fold_surplus)}pp, "
                f"n={summary.events}"
            )

            rows.append(
                {
                    "street": street_label,
                    "preflop_action": preflop_action,
                    "bet_classification": bet_classification,
                    "flop_texture": texture_label,
                    "players": players_label,
                    "bettor_position": bettor_position,
                    "spr_bucket": spr_bucket_label,
                    "situation": "Bluff",
                    "action": action_text,
                    "rank": rank,
                    "avg_bet_pct": summary.avg_ratio * 100.0,
                }
            )

        value_candidates: List[Tuple[str, str, BucketSummary]] = []
        for bucket_key, summary in summaries.items():
            if summary.events < MIN_EVENTS:
                continue
            if summary.avg_share_all <= 0:
                continue
            label = bucket_labels.get(bucket_key)
            if not label:
                continue
            value_candidates.append((bucket_key, label, summary))

        value_candidates.sort(
            key=lambda item: (-item[2].avg_share_all, -item[2].events),
        )

        for rank, (_, bucket_label, summary) in enumerate(value_candidates[:2]):
            action_text = (
                f"Bet {bucket_label} — adds {summary.avg_share_all:.2f}× pot, "
                f"villain continues {summary.continue_pct:.1f}% "
                f"(calls {summary.call_pct:.1f}%, raises {summary.raise_pct:.1f}%), "
                f"fold surplus {_format_fold_surplus(summary.fold_surplus)}pp, "
                f"n={summary.events}"
            )

            rows.append(
                {
                    "street": street_label,
                    "preflop_action": preflop_action,
                    "bet_classification": bet_classification,
                    "flop_texture": texture_label,
                    "players": players_label,
                    "bettor_position": bettor_position,
                    "spr_bucket": spr_bucket_label,
                    "situation": "Value",
                    "action": action_text,
                    "rank": rank,
                    "avg_bet_pct": summary.avg_ratio * 100.0,
                }
            )

    return rows


def build_action_recommendations(source: str | None = None) -> Dict[str, object]:
    """Build the full action-recommendations payload for a given data source."""

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()

    # For DriveHUD / default source we rely on the root response-matrix caches.
    matrix_source: str | None
    cache_subdir: str | None
    if not source or source.strip() in ("", "drivehud"):
        matrix_source = None
        cache_subdir = "drivehud"
    else:
        matrix_source = source.strip()
        cache_subdir = matrix_source

    flop_payload = load_flop_response_matrix(source=matrix_source)
    turn_payload = load_turn_response_matrix(source=matrix_source)
    river_payload = load_river_response_matrix(source=matrix_source)

    rows: List[Dict[str, object]] = []
    rows.extend(_build_flop_recommendations(flop_payload))
    rows.extend(_build_turn_or_river_recommendations(turn_payload, "Turn"))
    rows.extend(_build_turn_or_river_recommendations(river_payload, "River"))

    # Preserve existing filter metadata when present so the frontend can keep
    # using the same option labels. If no prior file exists we omit filters.
    filename = f"action_recommendations_{stake_policy.cache_token()}.json"
    cache_dir: Path = data_paths.cache_dir
    if cache_subdir:
        cache_dir = cache_dir / cache_subdir
    cache_dir.mkdir(parents=True, exist_ok=True)

    previous_filters = None
    previous_source_path = None
    previous_version = None

    existing_path = cache_dir / filename
    if existing_path.exists():
        try:
            with existing_path.open("r", encoding="utf-8") as handle:
                existing_payload = json.load(handle)
            if isinstance(existing_payload, Mapping):
                previous_filters = existing_payload.get("filters")
                previous_source_path = existing_payload.get("source_path")
                previous_version = existing_payload.get("version")
        except (OSError, json.JSONDecodeError):
            pass

    now = datetime.now(timezone.utc).isoformat()

    payload: Dict[str, object] = {
        "version": int(previous_version or 1),
        "stake_token": stake_policy.cache_token(),
        "source_path": previous_source_path or "",
        "generated_at": now,
        "updated_at": now,
        "rows": rows,
    }
    if previous_filters is not None:
        payload["filters"] = previous_filters

    return {"payload": payload, "path": str(existing_path)}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=str,
        default="drivehud",
        help="Data source key (drivehud, pokerstars_nl10, ...).",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build_action_recommendations(source=args.source)
    payload = result["payload"]
    path = Path(result["path"])

    json_text = json.dumps(payload, indent=2, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text, encoding="utf-8")

    print(f"Wrote {len(payload['rows'])} recommendation rows to {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
