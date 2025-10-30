"""Classification helpers for hero flop hand strength."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from poker_analytics.data.cards import parse_cards_text

CardTuple = Tuple[str, int, str]

PRIMARY_HAND_TYPES: Sequence[str] = [
    "Air",
    "Underpair",
    "Bottom Pair",
    "Middle Pair",
    "Top Pair",
    "Overpair",
    "Two Pair",
    "Trips/Set",
    "Straight",
    "Flush",
    "Full House",
    "Quads",
]

DRAW_CATEGORIES: Sequence[str] = ["Flush Draw", "OESD/DG"]

GROUP_DEFINITIONS: Sequence[Tuple[str, Sequence[str]]] = (
    ("Air", ("Air",)),
    ("Weak Pair", ("Underpair", "Bottom Pair", "Middle Pair")),
    ("Top Pair", ("Top Pair",)),
    ("Overpair", ("Overpair",)),
    ("Two Pair", ("Two Pair",)),
    ("Trips/Set", ("Trips/Set",)),
    ("Monster", ("Straight", "Flush", "Full House", "Quads")),
    ("Draw", ("Flush Draw", "OESD/DG")),
)


@dataclass(frozen=True)
class FlopHandClassification:
    primary: str
    has_flush_draw: bool
    has_oesd_dg: bool
    made_flush: bool
    made_straight: bool
    made_full_house: bool
    made_quads: bool


def classify_flop_hand(
    hole_cards: Sequence[CardTuple],
    board_cards: Sequence[CardTuple],
) -> FlopHandClassification:
    """Return the primary category and draw flags for a flop situation."""

    primary_map = _classify_primary(hole_cards, board_cards)
    return FlopHandClassification(
        primary=primary_map["primary"],
        has_flush_draw=bool(primary_map["flush_draw"]),
        has_oesd_dg=bool(primary_map["oesd_dg"]),
        made_flush=bool(primary_map["made_flush"]),
        made_straight=bool(primary_map["made_straight"]),
        made_full_house=bool(primary_map["made_full"]),
        made_quads=bool(primary_map["made_four"]),
    )


def parse_hole_cards(text: str | None) -> List[CardTuple]:
    return parse_cards_text(text or "")


def parse_board_cards(text: str | None) -> List[CardTuple]:
    return parse_cards_text(text or "")


def _has_flush(cards: Iterable[CardTuple]) -> bool:
    counts = Counter(suit for suit, _, _ in cards)
    return any(v >= 5 for v in counts.values())


def _has_flush_draw(hole: List[CardTuple], board: List[CardTuple]) -> bool:
    total = Counter()
    hole_suits = Counter(s for s, _, _ in hole)
    for s, _, _ in hole:
        total[s] += 1
    for s, _, _ in board:
        total[s] += 1
    return any(count >= 4 and hole_suits.get(suit, 0) > 0 for suit, count in total.items())


def _straight_info(
    hole: List[CardTuple],
    board: List[CardTuple],
) -> Tuple[bool, bool, bool]:
    ranks = {r for _, r, _ in hole + board}
    unique = set(ranks)
    if 14 in unique:
        unique.add(1)

    def _has_straight(values: set[int]) -> bool:
        for start in range(1, 11):
            seq = {start + offset for offset in range(5)}
            if seq <= values:
                return True
        return False

    if _has_straight(unique):
        return True, False, False

    inside_outs: set[int] = set()
    oesd = False

    for candidate in range(1, 15):
        if candidate in unique:
            continue
        augmented = unique | {candidate}
        if not _has_straight(augmented):
            continue
        treated = False
        for start in range(1, 11):
            seq = [start + offset for offset in range(5)]
            if set(seq) <= augmented and candidate in seq:
                if candidate == seq[0] or candidate == seq[-1]:
                    oesd = True
                else:
                    normalised = 14 if candidate == 1 else candidate
                    inside_outs.add(normalised)
                treated = True
                break
        if not treated and candidate == 1 and 14 not in unique:
            augmented_high = (augmented - {1}) | {14}
            for start in range(1, 11):
                seq = [start + offset for offset in range(5)]
                if set(seq) <= augmented_high and 14 in seq:
                    if 14 == seq[0] or 14 == seq[-1]:
                        oesd = True
                    else:
                        inside_outs.add(14)
                    break

    double_gutter = len(inside_outs) >= 2
    return False, oesd, double_gutter


def _classify_primary(
    hole: Sequence[CardTuple],
    board: Sequence[CardTuple],
) -> dict[str, bool | str]:
    combined = list(hole) + list(board)
    rank_counts = Counter(r for _, r, _ in combined)
    board_ranks = [r for _, r, _ in board]
    board_unique = sorted(set(board_ranks), reverse=True)
    hole_ranks = [r for _, r, _ in hole]
    hole_pair = len(hole_ranks) == 2 and hole_ranks[0] == hole_ranks[1]

    made_flush = _has_flush(combined)
    straight, oesd, double_gutter = _straight_info(list(hole), list(board))
    flush_draw = False if made_flush else _has_flush_draw(list(hole), list(board))

    counts_sorted = sorted(rank_counts.values(), reverse=True)
    made_four = any(v >= 4 for v in rank_counts.values())
    made_full = len(counts_sorted) >= 2 and counts_sorted[0] >= 3 and counts_sorted[1] >= 2
    made_trips_only = any(v >= 3 for v in rank_counts.values()) and not made_full and not made_four
    made_two_pair = sum(1 for v in rank_counts.values() if v >= 2) >= 2 and not made_full and not made_four

    max_board = board_unique[0] if board_unique else None
    second_board = board_unique[1] if len(board_unique) > 1 else None
    third_board = board_unique[2] if len(board_unique) > 2 else None

    overpair = False
    if hole_pair and max_board is not None and hole_ranks[0] > max_board and not made_two_pair and not made_full and not made_four:
        overpair = True

    top_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair):
        if max_board is not None and any(r == max_board for r in hole_ranks):
            top_pair = True

    middle_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair or top_pair):
        if second_board is not None and any(r == second_board for r in hole_ranks):
            middle_pair = True

    bottom_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair or top_pair or middle_pair):
        if third_board is not None and any(r == third_board for r in hole_ranks):
            bottom_pair = True

    underpair = False
    if hole_pair and max_board is not None and hole_ranks[0] < max_board and not made_full and not made_four and not made_trips_only:
        underpair = True

    if made_four:
        primary = "Quads"
    elif made_full:
        primary = "Full House"
    elif made_flush:
        primary = "Flush"
    elif straight:
        primary = "Straight"
    elif made_trips_only:
        primary = "Trips/Set"
    elif made_two_pair:
        primary = "Two Pair"
    elif overpair:
        primary = "Overpair"
    elif top_pair:
        primary = "Top Pair"
    elif middle_pair:
        primary = "Middle Pair"
    elif bottom_pair:
        primary = "Bottom Pair"
    elif underpair:
        primary = "Underpair"
    else:
        primary = "Air"

    oesd_or_double = oesd or double_gutter

    return {
        "primary": primary,
        "flush_draw": flush_draw,
        "oesd_dg": oesd_or_double,
        "made_flush": made_flush,
        "made_straight": straight,
        "made_full": made_full,
        "made_four": made_four,
    }


__all__ = [
    "FlopHandClassification",
    "PRIMARY_HAND_TYPES",
    "DRAW_CATEGORIES",
    "GROUP_DEFINITIONS",
    "classify_flop_hand",
    "parse_hole_cards",
    "parse_board_cards",
]
