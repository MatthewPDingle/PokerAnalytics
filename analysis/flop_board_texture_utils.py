
"""Helpers for classifying flop board textures."""

from __future__ import annotations

from typing import List, Tuple

SUIT_CHARS = {"s", "h", "d", "c"}
RANK_CHARS = {"2", "3", "4", "5", "6", "7", "8", "9", "t", "j", "q", "k", "a"}

TEXTURE_PREFIXES = {
    True: "Paired",
    False: "Unpaired",
}

TEXTURE_SUFFIXES = {
    1: "Monotone",
    2: "Two-tone",
    3: "Rainbow",
}

DEFAULT_TEXTURE = "Unpaired Rainbow"


def _normalise_token(token: str) -> Tuple[str, str] | tuple[()]:
    token = token.strip()
    if len(token) != 2:
        return ()
    suit = token[0].lower()
    rank = token[1].lower()
    if suit not in SUIT_CHARS or rank not in RANK_CHARS:
        return ()
    return suit, rank


def _parse_cards(cards_text: str | None) -> Tuple[List[str], List[str]] | tuple[()]:
    if not cards_text:
        return ()
    tokens = [tok for tok in cards_text.replace("​", " ").split() if tok.strip()]
    if len(tokens) != 3:
        return ()
    suits: List[str] = []
    ranks: List[str] = []
    for token in tokens:
        normalized = _normalise_token(token)
        if not normalized:
            return ()
        suit, rank = normalized
        suits.append(suit)
        ranks.append(rank)
    return suits, ranks


def derive_texture(cards_text: str | None) -> str:
    """Return a coarse texture bucket for a flop string."""

    parsed = _parse_cards(cards_text)
    if not parsed:
        return DEFAULT_TEXTURE

    suits, ranks = parsed
    is_paired = len(set(ranks)) < len(ranks)
    suit_diversity = len(set(suits))
    suffix = TEXTURE_SUFFIXES.get(suit_diversity, "Rainbow")
    prefix = TEXTURE_PREFIXES[is_paired]
    return f"{prefix} {suffix}"


__all__ = ["derive_texture", "TEXTURE_PREFIXES", "TEXTURE_SUFFIXES", "DEFAULT_TEXTURE"]
