"""Stake filtering utilities for DriveHUD-derived datasets."""

from __future__ import annotations

import math
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

from poker_analytics.config import resolve_allowed_big_blinds
from poker_analytics.data.cards import extract_big_blind
from poker_analytics.db import connect_readonly

if TYPE_CHECKING:
    from poker_analytics.data.drivehud import DriveHudDataSource


def _normalise_identifier(value: object | None) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _token_for_value(value: float) -> str:
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return formatted.replace(".", "p") if formatted else "0"


@dataclass(frozen=True)
class StakePolicy:
    """Represents the set of big blind stakes to include in analytics."""

    allowed_big_blinds: tuple[float, ...]
    rel_tolerance: float = 1e-3
    abs_tolerance: float = 5e-4

    @classmethod
    def from_environment(cls) -> "StakePolicy":
        allowed = tuple(sorted(set(resolve_allowed_big_blinds())))
        return cls(allowed_big_blinds=allowed)

    def is_unrestricted(self) -> bool:
        return len(self.allowed_big_blinds) == 0

    def matches(self, big_blind: Optional[float]) -> bool:
        if self.is_unrestricted():
            return True
        if big_blind is None:
            return False
        for target in self.allowed_big_blinds:
            if math.isclose(big_blind, target, rel_tol=self.rel_tolerance, abs_tol=self.abs_tolerance):
                return True
        return False

    def cache_token(self) -> str:
        if self.is_unrestricted():
            return "all-stakes"
        return "bb_" + "_".join(_token_for_value(value) for value in self.allowed_big_blinds)


@dataclass(frozen=True)
class StakeHandIdentifiers:
    """Lookup structure for filtering SQL-derived records by stake."""

    history_ids: frozenset[str]
    hand_numbers: frozenset[str]

    def contains(self, identifier: object | None) -> bool:
        if not self.history_ids and not self.hand_numbers:
            return False
        text = _normalise_identifier(identifier)
        if text is None:
            return False
        return text in self.history_ids or text in self.hand_numbers


@lru_cache(maxsize=8)
def _load_hand_identifiers_cached(
    db_path: str,
    allowed_big_blinds: tuple[float, ...],
    rel_tolerance: float,
    abs_tolerance: float,
) -> StakeHandIdentifiers:
    path = Path(db_path)
    history_ids: set[str] = set()
    hand_numbers: set[str] = set()

    if not path.exists():
        return StakeHandIdentifiers(frozenset(), frozenset())

    try:
        with connect_readonly(path) as conn:
            cursor = conn.execute("SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories")
            for row in cursor:
                hand_id, hand_number, hand_history = row
                if not hand_history:
                    continue
                try:
                    root = ET.fromstring(hand_history)
                except ET.ParseError:
                    continue
                big_blind = extract_big_blind(root)
                if big_blind is None:
                    continue
                if not any(
                    math.isclose(big_blind, target, rel_tol=rel_tolerance, abs_tol=abs_tolerance)
                    for target in allowed_big_blinds
                ):
                    continue
                normalised_id = _normalise_identifier(hand_id)
                if normalised_id:
                    history_ids.add(normalised_id)
                normalised_number = _normalise_identifier(hand_number)
                if normalised_number:
                    hand_numbers.add(normalised_number)
    except sqlite3.Error:
        return StakeHandIdentifiers(frozenset(), frozenset())

    return StakeHandIdentifiers(frozenset(history_ids), frozenset(hand_numbers))


def load_hand_identifiers_for_policy(
    source: "DriveHudDataSource",
    policy: StakePolicy,
) -> Optional[StakeHandIdentifiers]:
    """Return stake-filtered hand identifiers for SQL-based extracts."""

    if policy.is_unrestricted():
        return None
    allowed = tuple(sorted(policy.allowed_big_blinds))
    if not allowed:
        return None
    db_key = str(source.db_path.resolve())
    return _load_hand_identifiers_cached(db_key, allowed, policy.rel_tolerance, policy.abs_tolerance)


__all__ = ["StakePolicy", "StakeHandIdentifiers", "load_hand_identifiers_for_policy"]
