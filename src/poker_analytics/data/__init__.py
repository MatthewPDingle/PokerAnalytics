"""Reusable data definitions shared across analytics modules."""

from .bet_sizing import BET_SIZE_BUCKETS, bucket_for_ratio
from .textures import FLOP_TEXTURE_SPECS, detect_textures

__all__ = [
    "BET_SIZE_BUCKETS",
    "bucket_for_ratio",
    "FLOP_TEXTURE_SPECS",
    "detect_textures",
]
