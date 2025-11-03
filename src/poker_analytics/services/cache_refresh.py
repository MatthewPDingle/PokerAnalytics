"""Helpers for clearing and rebuilding cached analytics payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from poker_analytics.config import build_data_paths
from poker_analytics.services.flop_response_matrix_builder import write_flop_response_cache

CACHE_PATTERNS: tuple[str, ...] = (
    "flop_response_matrix*.json",
    "flop_hand_matrix*.json",
    "flop_responder_hand_matrix*.json",
    "flop_pot_contribution*.json",
    "line_explorer*.json",
    "line_responder_hand_matrix*.json",
    "line_query*.json",
)


def clear_flop_cache_files(patterns: Iterable[str] = CACHE_PATTERNS) -> list[Path]:
    """Delete cached flop/line payloads matching the supplied glob `patterns`."""

    data_paths = build_data_paths()
    cache_dir = data_paths.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    removed: list[Path] = []
    for pattern in patterns:
        for candidate in cache_dir.glob(pattern):
            try:
                candidate.unlink()
            except OSError:
                continue
            removed.append(candidate)
    return removed


def refresh_flop_caches(*, max_hands: Optional[int] = None, rebuild: bool = True) -> Optional[Path]:
    """Clear cached flop payloads and optionally rebuild the response matrix."""

    clear_flop_cache_files()

    if not rebuild:
        return None

    return write_flop_response_cache(max_hands=max_hands)


__all__ = ["CACHE_PATTERNS", "clear_flop_cache_files", "refresh_flop_caches"]
