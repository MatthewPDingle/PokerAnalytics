"""Shared helpers for flop bet-size bucket metadata and classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from poker_analytics.data.bet_sizing import BET_SIZE_BUCKETS, BetSizeBucket, bucket_for_ratio


@dataclass(frozen=True)
class BucketMeta:
    key: str
    label: str


BUCKET_METADATA: Sequence[BucketMeta] = (BucketMeta(key="check", label="Check"),) + tuple(
    BucketMeta(key=bucket.key, label=bucket.label) for bucket in BET_SIZE_BUCKETS
) + (
    BucketMeta(key="all_in", label="All-In"),
    BucketMeta(key="one_bb", label="1 BB"),
)

BUCKET_KEYS: Sequence[str] = [meta.key for meta in BUCKET_METADATA]


def bucket_keys_for_event(event: Mapping[str, object]) -> list[str]:
    """Return the bucket keys an event should contribute to."""

    keys: list[str] = []

    ratio = _extract_ratio(event)

    key = event.get("bucket_key")
    base_key: Optional[str]
    if isinstance(key, str) and key:
        base_key = key
    else:
        bucket = bucket_for_ratio(ratio)
        base_key = bucket.key if isinstance(bucket, BetSizeBucket) else None

    if base_key:
        keys.append(base_key)

    ratio_bucket = bucket_for_ratio(ratio)
    if ratio_bucket is not None and ratio_bucket.key and ratio_bucket.key != base_key:
        keys.append(ratio_bucket.key)

    if bool(event.get("is_check")):
        keys.append("check")

    if bool(event.get("is_all_in")):
        keys.append("all_in")
    if bool(event.get("is_one_bb")):
        keys.append("one_bb")

    return _dedupe_preserving_order(keys)


def _extract_ratio(event: Mapping[str, object]) -> Optional[float]:
    ratio_raw = event.get("ratio")
    try:
        return float(ratio_raw) if ratio_raw is not None else None
    except (TypeError, ValueError):
        return None


def _dedupe_preserving_order(keys: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key and key not in seen and key in BUCKET_KEYS:
            seen.add(key)
            ordered.append(key)
    return ordered


__all__ = ["BucketMeta", "BUCKET_METADATA", "BUCKET_KEYS", "bucket_keys_for_event"]
