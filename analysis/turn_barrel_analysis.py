#!/usr/bin/env python3
"""Analyse hero turn double barrels and their success rates."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

BET_BUCKETS: Sequence[Tuple[float, float, str]] = (
    (0.0, 0.40, "<40%"),
    (0.40, 0.60, "40-60%"),
    (0.60, 0.80, "60-80%"),
    (0.80, 1.10, "80-110%"),
    (1.10, math.inf, ">110%"),
)


@dataclass
class TurnBarrel:
    hand_id: str
    bet_c: int
    pot_before_c: int
    bucket: str
    opponents: int
    success: bool
    texture: str
    category: str


RANK_MAP = {
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


@dataclass
class Card:
    rank: int
    suit: str


def parse_card(token: Optional[str]) -> Optional[Card]:
    if not token:
        return None
    token = token.strip()
    if len(token) < 2:
        return None
    rank_char = token[0].upper()
    suit = token[1].lower()
    if rank_char == "1" and len(token) >= 3 and token[1] == "0":
        rank_char = "T"
        suit = token[2].lower()
    rank = RANK_MAP.get(rank_char)
    if rank is None:
        return None
    return Card(rank=rank, suit=suit)


def parse_cards(text: Optional[str]) -> List[Card]:
    if not text:
        return []
    parts = [p for p in text.replace("/", " ").split() if p]
    cards: List[Card] = []
    for part in parts:
        card = parse_card(part)
        if card:
            cards.append(card)
    return cards


def has_pair_or_better(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    combined = list(hero) + list(board)
    if len(combined) < 2:
        return False
    counts = Counter(card.rank for card in combined)
    return any(cnt >= 2 for cnt in counts.values())


def has_flush_draw(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    if not hero:
        return False
    combined = list(hero) + list(board)
    suit_counts = Counter(card.suit for card in combined)
    for suit, total in suit_counts.items():
        if total >= 4 and any(card.suit == suit for card in hero) and total < 5:
            return True
    return False


def has_straight_draw(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    if not hero:
        return False
    combined = list(hero) + list(board)
    ranks = {card.rank for card in combined}
    hero_ranks = {card.rank for card in hero}
    if 14 in ranks:
        ranks.add(1)
    if 14 in hero_ranks:
        hero_ranks.add(1)
    for start in range(1, 11):
        window = set(range(start, start + 5))
        if len(ranks & window) >= 4 and hero_ranks & window:
            # Ensure straight not already made (would be value)
            if len(ranks & window) == 4:
                return True
    return False


def classify_category(hero_cards: Sequence[Card], board_cards: Sequence[Card]) -> str:
    if has_pair_or_better(hero_cards, board_cards):
        return "Value"
    if has_flush_draw(hero_cards, board_cards) or has_straight_draw(hero_cards, board_cards):
        return "Draw"
    return "Air"


def bucketize(ratio: float) -> Optional[str]:
    if ratio <= 0 or math.isnan(ratio) or math.isinf(ratio):
        return None
    for low, high, label in BET_BUCKETS:
        if low <= ratio < high:
            return label
    return BET_BUCKETS[-1][2]


def load_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {hand_id: seat_no for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    seats_by_hand: Dict[str, set] = defaultdict(set)
    for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats"):
        seats_by_hand[hand_id].add(seat_no)
    flop_texture = {
        hand_id: (f"{rank_texture}-{suit_texture}").strip("-")
        for hand_id, suit_texture, rank_texture in cur.execute(
            "SELECT hand_id, suit_texture, rank_texture FROM v_board_flop_texture"
        )
    }
    hero_turn_flags = {
        hand_id: attempt
        for hand_id, attempt, _ in cur.execute("SELECT hand_id, attempt, made FROM v_hero_cbet_turn")
        if attempt == 1
    }
    hero_cards = {
        hand_id: (c1, c2)
        for hand_id, c1, c2 in cur.execute(
            """
            SELECT hc.hand_id, hc.c1, hc.c2
            FROM hole_cards hc
            JOIN seats s ON s.hand_id=hc.hand_id AND s.seat_no=hc.seat_no
            WHERE s.is_hero=1
            """
        )
    }
    board_map = {
        hand_id: (flop, turn)
        for hand_id, flop, turn in cur.execute(
            "SELECT hand_id, board_flop, board_turn FROM hands"
        )
    }
    return hero_seat, seats_by_hand, flop_texture, hero_turn_flags, hero_cards, board_map


def load_actions(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, int]]]:
    cur = conn.cursor()
    actions: Dict[str, List[Dict[str, int]]] = defaultdict(list)
    for row in cur.execute(
        """
        SELECT hand_id, ordinal, street, actor_seat, action, inc_c, pot_before_c
        FROM actions ORDER BY hand_id, ordinal
        """
    ):
        hand_id, ordinal, street, actor_seat, action, inc_c, pot_before_c = row
        actions[hand_id].append(
            {
                "ordinal": ordinal,
                "street": street,
                "actor": actor_seat,
                "action": action,
                "inc": inc_c or 0,
                "pot": pot_before_c or 0,
            }
        )
    return actions


def opponents_before_actions(
    hero_seat: Dict[str, int], seats_by_hand: Dict[str, set], actions: Dict[str, List[Dict[str, int]]]
) -> Dict[Tuple[str, int], int]:
    state: Dict[Tuple[str, int], int] = {}
    for hand_id, acts in actions.items():
        in_hand = set(seats_by_hand.get(hand_id, set()))
        hero = hero_seat.get(hand_id)
        for act in acts:
            if hero in in_hand:
                opps = len([s for s in in_hand if s != hero])
            else:
                opps = len(in_hand)
            state[(hand_id, act["ordinal"])] = opps
            if act["action"] == "fold":
                in_hand.discard(act["actor"])
    return state


def find_turn_barrels(
    hero_seat: Dict[str, int],
    flop_texture: Dict[str, str],
    hero_flags: Dict[str, int],
    hero_cards: Dict[str, Tuple[Optional[str], Optional[str]]],
    board_map: Dict[str, Tuple[Optional[str], Optional[str]]],
    actions_by_hand: Dict[str, List[Dict[str, int]]],
    opponents_state: Dict[Tuple[str, int], int],
) -> List[TurnBarrel]:
    barrels: List[TurnBarrel] = []
    for hand_id, actions in actions_by_hand.items():
        if hero_flags.get(hand_id) != 1:
            continue  # hero had chance but didn't bet
        hero = hero_seat.get(hand_id)
        if hero is None:
            continue
        hero_card_tokens = hero_cards.get(hand_id)
        board_tokens = board_map.get(hand_id)
        if not hero_card_tokens or not board_tokens:
            continue
        flop_cards = parse_cards(board_tokens[0])
        turn_card = parse_card(board_tokens[1]) if board_tokens[1] else None
        board_cards = flop_cards + ([turn_card] if turn_card else [])
        hero_card_objs = [c for c in (parse_card(hero_card_tokens[0]), parse_card(hero_card_tokens[1])) if c]
        if len(hero_card_objs) < 2 or len(board_cards) < 3:
            continue
        category = classify_category(hero_card_objs, board_cards)
        for idx, act in enumerate(actions):
            if act["street"] != "turn" or act["actor"] != hero:
                continue
            if act["action"] not in {"bet", "raise", "all-in"}:
                break  # hero checked; no barrel
            pot_before = act["pot"]
            bet = act["inc"]
            if pot_before <= 0 or bet <= 0:
                break
            ratio = bet / pot_before
            bucket = bucketize(ratio)
            if not bucket:
                break
            success = True
            for later in actions[idx + 1 :]:
                if later["street"] != "turn":
                    break
                if later["actor"] == hero:
                    continue
                if later["action"] in {"call", "bet", "raise", "all-in"}:
                    success = False
                    break
            opponents = opponents_state.get((hand_id, act["ordinal"]), 0)
            texture = flop_texture.get(hand_id, "unknown")
            barrels.append(
                TurnBarrel(
                    hand_id=hand_id,
                    bet_c=bet,
                    pot_before_c=pot_before,
                    bucket=bucket,
                    opponents=opponents,
                    success=success,
                    texture=texture,
                    category=category,
                )
            )
            break  # only first hero turn action matters
    return barrels


def summarize(barrels: List[TurnBarrel]) -> None:
    total = len(barrels)
    success = sum(1 for b in barrels if b.success)
    print(f"Hero turn barrels: {total}")
    if total:
        print(f"Success rate: {success/total:.3f}\n")

    bucket_stats: Dict[str, Counter] = defaultdict(Counter)
    for b in barrels:
        bucket_stats[b.bucket]["attempts"] += 1
        if b.success:
            bucket_stats[b.bucket]["success"] += 1
    print("Success by bet-size bucket:")
    for _, _, label in BET_BUCKETS:
        data = bucket_stats.get(label)
        if not data:
            continue
        rate = data["success"] / data["attempts"]
        print(f"  {label:>7}: {data['attempts']:4d} attempts, {rate:.3f} success")
    print()

    texture_stats: Dict[str, Counter] = defaultdict(Counter)
    for b in barrels:
        texture_stats[b.texture]["attempts"] += 1
        if b.success:
            texture_stats[b.texture]["success"] += 1
    print("Success by flop texture:")
    for texture, counts in sorted(texture_stats.items(), key=lambda kv: -kv[1]["attempts"]):
        if counts["attempts"] < 5:
            continue
        rate = counts["success"] / counts["attempts"]
        print(f"  {texture:<16} {counts['attempts']:4d} attempts, {rate:.3f} success")
    print()

    opp_stats: Dict[int, Counter] = defaultdict(Counter)
    for b in barrels:
        opp_stats[b.opponents]["attempts"] += 1
        if b.success:
            opp_stats[b.opponents]["success"] += 1
    print("Success by opponents remaining:")
    for opps in sorted(opp_stats):
        counts = opp_stats[opps]
        rate = counts["success"] / counts["attempts"]
        print(f"  {opps} opp(s): {counts['attempts']:4d} attempts, {rate:.3f} success")

    category_stats: Dict[str, Counter] = defaultdict(Counter)
    for b in barrels:
        category_stats[b.category]["attempts"] += 1
        if b.success:
            category_stats[b.category]["success"] += 1
    print("\nSuccess by hand category:")
    for category, counts in sorted(category_stats.items(), key=lambda kv: -kv[1]["attempts"]):
        rate = counts["success"] / counts["attempts"]
        print(f"  {category:<6} {counts['attempts']:4d} attempts, {rate:.3f} success")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        hero_seat, seats_by_hand, textures, hero_flags, hero_cards, board_map = load_maps(conn)
        actions = load_actions(conn)
        opp_state = opponents_before_actions(hero_seat, seats_by_hand, actions)
        barrels = find_turn_barrels(hero_seat, textures, hero_flags, hero_cards, board_map, actions, opp_state)
        summarize(barrels)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
