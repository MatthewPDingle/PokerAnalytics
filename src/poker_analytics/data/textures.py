"""Canonical flop board texture predicates.

These predicates originate from the exploratory work in
`analysis/flop_board_texture_explorer.ipynb`. They provide reusable signals
for dashboards, filters, and aggregations. Parsing is designed to be tolerant
of the historical formats observed in DriveHUD exports (rank-first or
suit-first tokens, optional separators, and the `10` vs `T` rank difference).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

RANK_VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}

SUIT_CHARS = {"C", "D", "H", "S"}
BROADWAY_RANKS = {"J", "Q", "K", "A"}


@dataclass(frozen=True)
class Card:
    """Simple representation of a flop card."""

    rank: str  # single uppercase character, e.g. "A"
    suit: str  # single uppercase character, e.g. "S"

    @property
    def rank_value(self) -> int:
        return RANK_VALUES[self.rank]


@dataclass(frozen=True)
class TextureSpec:
    """Defines a named flop texture predicate."""

    key: str
    title: str
    description: str
    predicate: Callable[[Sequence[Card]], bool]

def _parse_token(raw: str) -> Optional[Card]:
    token = raw.strip().replace("/", "")
    if not token:
        return None

    token = token.upper()
    # Handle length > 2 when rank is "10" or stray characters.
    token = token.replace("10", "T")
    if len(token) < 2:
        return None

    first, second = token[0], token[1]
    rank: Optional[str] = None
    suit: Optional[str] = None

    if first in RANK_VALUES and second in SUIT_CHARS:
        rank = first
        suit = second
    elif first in SUIT_CHARS and second in RANK_VALUES:
        suit = first
        rank = second
    else:
        # Attempt to find suit in last position when extra characters exist.
        if token[-1] in SUIT_CHARS and token[0] in RANK_VALUES:
            rank = token[0]
            suit = token[-1]

    if not rank or not suit:
        return None

    return Card(rank=rank, suit=suit)


def parse_flop(text: Optional[str]) -> List[Card]:
    """Parse a DriveHUD-like flop string into `Card` objects."""

    if not text:
        return []
    parts = [part for part in text.replace("\t", " ").split() if part]
    cards = [_parse_token(part) for part in parts]
    return [card for card in cards if card is not None]


def _has_pair(cards: Sequence[Card]) -> bool:
    ranks = [card.rank for card in cards]
    return len(ranks) != len(set(ranks))


def _is_connected(cards: Sequence[Card]) -> bool:
    if len(cards) != 3:
        return False
    values = sorted(card.rank_value for card in cards)
    if values[-1] - values[0] <= 4:
        return True
    if 14 in values:
        wheel = sorted(1 if v == 14 else v for v in values)
        return wheel[-1] - wheel[0] <= 4
    return False


def _two_broadways(cards: Sequence[Card]) -> bool:
    return sum(1 for card in cards if card.rank in BROADWAY_RANKS) >= 2


FLOP_TEXTURE_SPECS: Sequence[TextureSpec] = (
    TextureSpec(
        key="rainbow",
        title="Rainbow Flops",
        description="Exactly three suits represented on the flop.",
        predicate=lambda cards: len({card.suit for card in cards}) == 3,
    ),
    TextureSpec(
        key="monotone",
        title="Monotone Flops",
        description="All three cards share the same suit.",
        predicate=lambda cards: len({card.suit for card in cards}) == 1 and len(cards) == 3,
    ),
    TextureSpec(
        key="two_tone",
        title="Two-Tone Flops",
        description="Exactly two suits present.",
        predicate=lambda cards: len({card.suit for card in cards}) == 2,
    ),
    TextureSpec(
        key="paired",
        title="Paired Flops",
        description="Any rank appears at least twice.",
        predicate=_has_pair,
    ),
    TextureSpec(
        key="connected",
        title="Connected Flops",
        description="Rank spread within four cards (Ace can play low).",
        predicate=_is_connected,
    ),
    TextureSpec(
        key="ace_high",
        title="Ace-High Flops",
        description="An Ace is present and is the highest rank.",
        predicate=lambda cards: bool(cards) and max(card.rank_value for card in cards) == 14,
    ),
    TextureSpec(
        key="low",
        title="Low Flops (All <= Ten)",
        description="No card higher than Ten.",
        predicate=lambda cards: bool(cards) and all(card.rank_value <= 10 for card in cards),
    ),
    TextureSpec(
        key="high",
        title="High Flops (>=2 Broadways)",
        description="At least two Broadway ranks (J, Q, K, A).",
        predicate=_two_broadways,
    ),
)


def detect_textures(flop_text: Optional[str]) -> List[TextureSpec]:
    """Return the list of texture specs that match the provided flop string."""

    cards = parse_flop(flop_text)
    if len(cards) != 3:
        return []
    return [spec for spec in FLOP_TEXTURE_SPECS if spec.predicate(cards)]


def texture_keys(flop_text: Optional[str]) -> List[str]:
    """Return the matching texture keys for convenience in serialization."""

    return [spec.key for spec in detect_textures(flop_text)]


def texture_titles(specs: Iterable[TextureSpec] = FLOP_TEXTURE_SPECS) -> List[str]:
    """Return the ordered list of texture titles (for selectors/labels)."""

    return [spec.title for spec in specs]


__all__ = [
    "Card",
    "TextureSpec",
    "FLOP_TEXTURE_SPECS",
    "detect_textures",
    "parse_flop",
    "texture_keys",
    "texture_titles",
]
