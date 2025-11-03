"""Shared helpers for classifying preflop aggression levels."""

from __future__ import annotations

from typing import Mapping, Sequence

PREFLOP_ANY_KEY = "any"
PREFLOP_OPTIONS: Sequence[Mapping[str, str]] = (
    {"key": PREFLOP_ANY_KEY, "label": "All Preflop Pots"},
    {"key": "limped", "label": "Limped Pot (No Raise)"},
    {"key": "single_raise", "label": "Single-Raise Pot"},
    {"key": "three_bet_plus", "label": "3-Bet+ Pot"},
)
PREFLOP_ORDER = {option["key"]: index for index, option in enumerate(PREFLOP_OPTIONS)}


def preflop_bucket(level: object) -> str:
    """Return the canonical bucket for a preflop aggression level."""

    try:
        count = int(level)
    except (TypeError, ValueError):
        count = 0

    if count <= 0:
        return "limped"
    if count == 1:
        return "single_raise"
    return "three_bet_plus"


def preflop_keys(level: object) -> list[str]:
    """Return the set of preflop keys an event contributes to (including 'any')."""

    bucket = preflop_bucket(level)
    keys = [PREFLOP_ANY_KEY]
    if bucket not in keys:
        keys.append(bucket)
    return keys


__all__ = ["PREFLOP_ANY_KEY", "PREFLOP_OPTIONS", "PREFLOP_ORDER", "preflop_bucket", "preflop_keys"]
