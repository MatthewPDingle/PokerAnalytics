"""Utilities for parsing card strings and hand metadata from DriveHUD exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Tuple

SUITS = {"S", "H", "D", "C"}
CARD_RANKS = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

_BB_REGEX = re.compile(r"\$?([0-9]*\.?[0-9]+)/\$?([0-9]*\.?[0-9]+)")


def parse_cards_text(text: str | None) -> List[Tuple[str, int, str]]:
    """Parse DriveHUD two-character card tokens into structured tuples.

    Returns a list of tuples in the form ``(suit, rank_value, original_token)``.
    ``original_token`` preserves the raw input (e.g., ``"HK"``).
    The function is intentionally strict: encountering malformed tokens
    results in an empty list, mirroring the legacy notebook behaviour.
    """

    if not text:
        return []
    parts = [p.strip() for p in text.split() if p.strip()]
    cards: List[Tuple[str, int, str]] = []
    for part in parts:
        if len(part) != 2:
            return []
        suit, rank = part[0].upper(), part[1].upper()
        if suit not in SUITS or rank not in CARD_RANKS:
            return []
        cards.append((suit, CARD_RANKS[rank], f"{suit}{rank}"))
    return cards


def extract_big_blind(root: ET.Element) -> float | None:
    """Extract the big blind amount from a DriveHUD hand history XML tree."""

    for xpath in ("./general/gametype", ".//game/general/gametype"):
        node = root.find(xpath)
        if node is not None and node.text:
            match = _BB_REGEX.search(node.text)
            if match:
                try:
                    return float(match.group(2))
                except ValueError:
                    pass
    for xpath in ("./general/bigblind", ".//game/general/bigblind"):
        node = root.find(xpath)
        if node is not None and node.text:
            try:
                return float(node.text)
            except ValueError:
                pass
    return None


__all__ = ["parse_cards_text", "extract_big_blind", "SUITS", "CARD_RANKS"]
