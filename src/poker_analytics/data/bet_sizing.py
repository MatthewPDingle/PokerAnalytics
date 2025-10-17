"""Canonical flop bet-size buckets shared across analyses.

Derived from the legacy `flop_cbet_explorer.ipynb` notebook. Buckets are
expressed as the ratio of wager to pot immediately before the action. The
upper bound is exclusive so buckets do not overlap; values larger than the
final bound fall into the terminal bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class BetSizeBucket:
    """Represents a normalized bet-size range."""

    key: str
    label: str
    lower: float
    upper: float

    def contains(self, ratio: float) -> bool:
        """Return True if `ratio` belongs to this bucket."""

        if ratio < self.lower:
            return False
        if self.upper == float("inf"):
            return ratio >= self.lower
        return ratio < self.upper


BET_SIZE_BUCKETS: Sequence[BetSizeBucket] = (
    BetSizeBucket(key="pct_0_25", label="0-25%", lower=0.00, upper=0.25),
    BetSizeBucket(key="pct_25_40", label="25-40%", lower=0.25, upper=0.40),
    BetSizeBucket(key="pct_40_60", label="40-60%", lower=0.40, upper=0.60),
    BetSizeBucket(key="pct_60_80", label="60-80%", lower=0.60, upper=0.80),
    BetSizeBucket(key="pct_80_100", label="80-100%", lower=0.80, upper=1.00),
    BetSizeBucket(key="pct_100_125", label="100-125%", lower=1.00, upper=1.25),
    BetSizeBucket(key="pct_125_200", label="125-200%", lower=1.25, upper=2.00),
    BetSizeBucket(key="pct_200_300", label="200-300%", lower=2.00, upper=3.00),
    BetSizeBucket(key="pct_300_plus", label="300%+", lower=3.00, upper=float("inf")),
)


def bucket_for_ratio(ratio: Optional[float]) -> Optional[BetSizeBucket]:
    """Return the bucket that contains the given bet-to-pot `ratio`.

    Values that are `None`, NaN, or negative return `None` so callers can
    decide how to handle incomplete events.
    """

    if ratio is None:
        return None
    if ratio != ratio:  # NaN check without importing math
        return None
    if ratio < 0:
        return None

    for bucket in BET_SIZE_BUCKETS:
        if bucket.contains(ratio):
            return bucket
    return BET_SIZE_BUCKETS[-1]


def bucket_labels(buckets: Iterable[BetSizeBucket] = BET_SIZE_BUCKETS) -> list[str]:
    """Convenience helper for chart legends and dropdown options."""

    return [bucket.label for bucket in buckets]


__all__ = ["BetSizeBucket", "BET_SIZE_BUCKETS", "bucket_for_ratio", "bucket_labels"]
