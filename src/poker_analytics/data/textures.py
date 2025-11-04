"""Canonical postflop board texture predicates.

These predicates originate from the exploratory work in
`analysis/flop_board_texture_explorer.ipynb`. They provide reusable signals
for dashboards, filters, and aggregations. Parsing is designed to be tolerant
of the historical formats observed in DriveHUD exports (rank-first or
suit-first tokens, optional separators, and the `10` vs `T` rank difference).
"""

from __future__ import annotations

from collections import Counter
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
    """Simple representation of a community card."""

    rank: str  # single uppercase character, e.g. "A"
    suit: str  # single uppercase character, e.g. "S"

    @property
    def rank_value(self) -> int:
        return RANK_VALUES[self.rank]


@dataclass(frozen=True)
class TextureSpec:
    """Defines a named board texture predicate."""

    key: str
    title: str
    description: str
    predicate: Callable[[Sequence[Card]], bool]


def _parse_token(raw: str) -> Optional[Card]:
    token = raw.strip().replace("/", "")
    if not token:
        return None

    token = token.upper()
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
        if token[-1] in SUIT_CHARS and token[0] in RANK_VALUES:
            rank = token[0]
            suit = token[-1]

    if not rank or not suit:
        return None

    return Card(rank=rank, suit=suit)


def _parse_cards(text: Optional[str]) -> List[Card]:
    if not text:
        return []
    parts = [part for part in text.replace("\t", " ").split() if part]
    cards = [_parse_token(part) for part in parts]
    return [card for card in cards if card is not None]


def parse_flop(text: Optional[str]) -> List[Card]:
    """Parse a DriveHUD-like flop string into `Card` objects."""

    return _parse_cards(text)


def parse_turn(text: Optional[str]) -> List[Card]:
    """Parse a DriveHUD-like turn board string (flop + turn) into `Card` objects."""

    return _parse_cards(text)


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


def _suit_counts(cards: Sequence[Card]) -> Counter[str]:
    return Counter(card.suit for card in cards)


def _rank_counts(cards: Sequence[Card]) -> Counter[str]:
    return Counter(card.rank for card in cards)


def _rank_values(cards: Sequence[Card]) -> List[int]:
    return [card.rank_value for card in cards]


def _values_wheel_adjusted(cards: Sequence[Card]) -> List[int]:
    values = _rank_values(cards)
    if any(value == 14 for value in values):
        return [1 if value == 14 else value for value in values]
    return values


def _connected_le_six(cards: Sequence[Card]) -> bool:
    if len(cards) != 4:
        return False
    values = sorted(_rank_values(cards))
    if not values:
        return False
    spread_standard = values[-1] - values[0]
    wheel_values = sorted(_values_wheel_adjusted(cards))
    spread_wheel = wheel_values[-1] - wheel_values[0]
    return min(spread_standard, spread_wheel) <= 6


def _has_sequence(cards: Sequence[Card], length: int) -> bool:
    if len(cards) < length:
        return False
    values_standard = sorted(set(_rank_values(cards)))
    if _sequence_in_values(values_standard, length):
        return True
    if any(card.rank_value == 14 for card in cards):
        wheel_values = sorted(set(_values_wheel_adjusted(cards)))
        return _sequence_in_values(wheel_values, length)
    return False


def _sequence_in_values(values: Sequence[int], length: int) -> bool:
    if len(values) < length:
        return False
    value_set = set(values)
    min_value = min(values)
    max_value = max(values)
    for start in range(min_value, max_value - length + 2):
        if all((start + offset) in value_set for offset in range(length)):
            return True
    return False


def _paired_exactly_one(cards: Sequence[Card]) -> bool:
    counts = _rank_counts(cards)
    pair_counts = sum(1 for value in counts.values() if value == 2)
    return pair_counts == 1 and all(value <= 2 for value in counts.values())


def _paired_exactly_two(cards: Sequence[Card]) -> bool:
    counts = _rank_counts(cards)
    return sum(1 for value in counts.values() if value == 2) == 2


def _trips_present(cards: Sequence[Card]) -> bool:
    counts = _rank_counts(cards)
    return any(value == 3 for value in counts.values())


def _quads_present(cards: Sequence[Card]) -> bool:
    counts = _rank_counts(cards)
    return any(value == 4 for value in counts.values())


def _ace_high(cards: Sequence[Card]) -> bool:
    if not cards:
        return False
    values = _rank_values(cards)
    return max(values) == 14 and 14 in values


def _low_board(cards: Sequence[Card]) -> bool:
    if not cards:
        return False
    return all(card.rank_value <= 10 for card in cards)


def _high_board(cards: Sequence[Card]) -> bool:
    if not cards:
        return False
    return sum(1 for card in cards if card.rank_value >= 10) >= 3


FLOP_TEXTURE_SPECS: Sequence[TextureSpec] = (
    TextureSpec(
        key="rainbow",
        title="Rainbow Flops",
        description="Exactly three suits represented on the flop.",
        predicate=lambda cards: len(_suit_counts(cards)) == 3,
    ),
    TextureSpec(
        key="monotone",
        title="Monotone Flops",
        description="All three cards share the same suit.",
        predicate=lambda cards: len(_suit_counts(cards)) == 1 and len(cards) == 3,
    ),
    TextureSpec(
        key="two_tone",
        title="Two-Tone Flops",
        description="Exactly two suits present.",
        predicate=lambda cards: len(_suit_counts(cards)) == 2,
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
        title="Low Flops (All ≤ Ten)",
        description="No card higher than Ten.",
        predicate=lambda cards: bool(cards) and all(card.rank_value <= 10 for card in cards),
    ),
    TextureSpec(
        key="high",
        title="High Flops (≥2 Broadways)",
        description="At least two Broadway ranks (J, Q, K, A).",
        predicate=_two_broadways,
    ),
)


TURN_TEXTURE_SPECS: Sequence[TextureSpec] = (
    TextureSpec(
        key="rainbow",
        title="Rainbow Turns",
        description="All four cards are different suits.",
        predicate=lambda cards: len(_suit_counts(cards)) == 4,
    ),
    TextureSpec(
        key="two_tone",
        title="Two-Tone Turns",
        description="Exactly two suits present.",
        predicate=lambda cards: len(_suit_counts(cards)) == 2,
    ),
    TextureSpec(
        key="three_suited",
        title="Three-Suited Turns",
        description="Three cards share the same suit (but not monotone).",
        predicate=lambda cards: max(_suit_counts(cards).values() or [0]) == 3,
    ),
    TextureSpec(
        key="monotone",
        title="Monotone Turns",
        description="All four cards share the same suit.",
        predicate=lambda cards: len(_suit_counts(cards)) == 1 and len(cards) == 4,
    ),
    TextureSpec(
        key="connected_le6",
        title="Connected (≤6 Gap)",
        description="Rank spread between highest and lowest is six or fewer (wheel-aware).",
        predicate=_connected_le_six,
    ),
    TextureSpec(
        key="three_connected",
        title="Three Connected Ranks",
        description="At least three sequential ranks without gaps.",
        predicate=lambda cards: _has_sequence(cards, 3),
    ),
    TextureSpec(
        key="four_connected",
        title="Four Connected Ranks",
        description="All four cards form a straight without gaps.",
        predicate=lambda cards: _has_sequence(cards, 4),
    ),
    TextureSpec(
        key="paired",
        title="Paired Turn",
        description="One rank appears exactly twice (no trips or double pairs).",
        predicate=_paired_exactly_one,
    ),
    TextureSpec(
        key="double_paired",
        title="Double Paired Turn",
        description="Two ranks each appear exactly twice.",
        predicate=_paired_exactly_two,
    ),
    TextureSpec(
        key="trips",
        title="Trips on Board",
        description="Some rank appears exactly three times.",
        predicate=_trips_present,
    ),
    TextureSpec(
        key="quads",
        title="Quads on Board",
        description="Some rank appears exactly four times.",
        predicate=_quads_present,
    ),
    TextureSpec(
        key="ace_high",
        title="Ace-High Turns",
        description="An Ace is present and is the highest rank.",
        predicate=_ace_high,
    ),
    TextureSpec(
        key="low",
        title="Low Turns (All ≤ Ten)",
        description="All ranks Ten or lower.",
        predicate=_low_board,
    ),
    TextureSpec(
        key="high",
        title="High Turns (≥3 Tens+)",
        description="At least three cards Ten or higher.",
        predicate=_high_board,
    ),
)


def detect_textures(flop_text: Optional[str]) -> List[TextureSpec]:
    """Return the list of texture specs that match the provided flop string."""

    cards = parse_flop(flop_text)
    if len(cards) != 3:
        return []
    return [spec for spec in FLOP_TEXTURE_SPECS if spec.predicate(cards)]


def detect_turn_textures(turn_text: Optional[str]) -> List[TextureSpec]:
    """Return the list of texture specs that match the provided turn string."""

    cards = parse_turn(turn_text)
    if len(cards) != 4:
        return []
    return [spec for spec in TURN_TEXTURE_SPECS if spec.predicate(cards)]


def texture_keys(flop_text: Optional[str]) -> List[str]:
    """Return the matching flop texture keys for convenience in serialization."""

    return [spec.key for spec in detect_textures(flop_text)]


def turn_texture_keys(turn_text: Optional[str]) -> List[str]:
    """Return the matching turn texture keys for convenience in serialization."""

    return [spec.key for spec in detect_turn_textures(turn_text)]


def texture_titles(specs: Iterable[TextureSpec] = FLOP_TEXTURE_SPECS) -> List[str]:
    """Return the ordered list of texture titles (for selectors/labels)."""

    return [spec.title for spec in specs]


__all__ = [
    "Card",
    "TextureSpec",
    "FLOP_TEXTURE_SPECS",
    "TURN_TEXTURE_SPECS",
    "detect_textures",
    "detect_turn_textures",
    "parse_flop",
    "parse_turn",
    "texture_keys",
    "turn_texture_keys",
    "texture_titles",
]
