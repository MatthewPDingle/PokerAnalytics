"""Loaders that aggregate flop betting data from DriveHUD."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional

from poker_analytics.data.bet_sizing import BET_SIZE_BUCKETS, bucket_for_ratio
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.data.textures import FLOP_TEXTURE_SPECS, texture_keys

FLOP_SUMMARY_QUERY = """
    SELECT h.hand_id,
           h.board_flop AS board_flop,
           a.amount AS bet_ratio
    FROM hands h
    JOIN actions a ON a.hand_id = h.hand_id
    JOIN seats s ON s.hand_id = h.hand_id AND s.player_name = a.actor
    WHERE a.street = 'flop'
      AND s.is_hero = 1
      AND a.action IN ('bet', 'raise')
"""


def _normalise_ratio(value: object | None) -> Optional[float]:
    if value is None:
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return None
    if ratio < 0:
        return None
    return ratio


def load_flop_bet_summary(source: Optional[DriveHudDataSource] = None) -> dict:
    """Return aggregated flop bet information grouped by canonical buckets and textures."""

    source = source or DriveHudDataSource.from_defaults()
    if not source.is_available():
        return _empty_summary()

    bucket_counts: Counter[str] = Counter()
    texture_counts: Counter[str] = Counter()
    events = 0

    try:
        rows = source.rows(FLOP_SUMMARY_QUERY)
    except Exception:
        return _empty_summary()

    for row in rows:
        ratio = _normalise_ratio(row.get("bet_ratio"))
        bucket = bucket_for_ratio(ratio)
        if bucket is not None:
            bucket_counts[bucket.key] += 1
        textures = texture_keys(row.get("board_flop"))
        for key in textures:
            texture_counts[key] += 1
        events += 1

    return {
        "events": events,
        "buckets": [
            {
                "key": bucket.key,
                "label": bucket.label,
                "count": bucket_counts.get(bucket.key, 0),
            }
            for bucket in BET_SIZE_BUCKETS
        ],
        "textures": [
            {
                "key": spec.key,
                "title": spec.title,
                "count": texture_counts.get(spec.key, 0),
            }
            for spec in FLOP_TEXTURE_SPECS
        ],
    }


def _empty_summary() -> dict:
    return {
        "events": 0,
        "buckets": [
            {"key": bucket.key, "label": bucket.label, "count": 0}
            for bucket in BET_SIZE_BUCKETS
        ],
        "textures": [
            {"key": spec.key, "title": spec.title, "count": 0}
            for spec in FLOP_TEXTURE_SPECS
        ],
    }


__all__ = ["load_flop_bet_summary", "FLOP_SUMMARY_QUERY"]
