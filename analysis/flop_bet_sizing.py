#!/usr/bin/env python3
"""Hero flop bet sizing analysis using normalized DriveHUD warehouse data.

This script reproduces the c-bet-with-air study directly from the warehouse,
so it can be re-run after each ingest. It focuses on situations where hero
bets or raises the flop without a made hand or strong draw, and reports how
often opponents fold grouped by bet size bucket and board texture.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

# Buckets for bet size as % of pot (expressed as decimal ratios)
BET_BUCKETS: Sequence[Tuple[float, float, str]] = (
    (0.0, 0.25, "<25%"),
    (0.25, 0.40, "25-40%"),
    (0.40, 0.60, "40-60%"),
    (0.60, 0.80, "60-80%"),
    (0.80, 1.10, "80-110%"),
    (1.10, math.inf, ">110%"),
)

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
    rank_char, suit = token[0].upper(), token[1].lower()
    if rank_char == "1" and len(token) >= 3 and token[1] == "0":
        rank_char = "T"
        suit = token[2].lower() if len(token) >= 3 else suit
    rank = RANK_MAP.get(rank_char)
    if rank is None:
        return None
    return Card(rank=rank, suit=suit)


def parse_cards(text: Optional[str]) -> List[Card]:
    if not text:
        return []
    parts = [p for p in text.replace("/", " ").split() if p]
    return [c for p in parts if (c := parse_card(p))]


def has_pair_or_better(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    if len(hero) < 2:
        return False
    if hero[0].rank == hero[1].rank:
        return True
    board_ranks = {c.rank for c in board}
    return any(card.rank in board_ranks for card in hero)


def has_flush_draw(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    if not hero:
        return False
    hero_suits = Counter(card.suit for card in hero)
    board_suits = Counter(card.suit for card in board)
    for suit, count in hero_suits.items():
        if count and count + board_suits[suit] >= 4:
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
            return True
    return False


def hero_has_air(hero: Sequence[Card], board: Sequence[Card]) -> bool:
    return not (has_pair_or_better(hero, board) or has_flush_draw(hero, board) or has_straight_draw(hero, board))


def board_texture(board: Sequence[Card]) -> str:
    if len(board) < 3:
        return "unknown"
    suits = {card.suit for card in board}
    ranks = [card.rank for card in board]
    rank_set = set(ranks)
    pair = len(rank_set) <= 2
    if len(suits) == 1:
        suit_tex = "Monotone"
    elif len(suits) == 2:
        suit_tex = "Two-tone"
    else:
        suit_tex = "Rainbow"
    if pair:
        return f"Paired {suit_tex}"
    broadway = sum(1 for r in ranks if r >= 11)
    ranks_for_conn = set(rank_set)
    if 14 in ranks_for_conn:
        ranks_for_conn.add(1)
    connected = any({start, start + 1, start + 2}.issubset(ranks_for_conn) for start in range(2, 11))
    if suit_tex == "Monotone":
        return "Monotone"
    if connected:
        return f"Connected {suit_tex}"
    if broadway >= 2:
        return "Broadway heavy"
    return f"Dry {suit_tex}"


def bucketize(bet_ratio: Optional[float]) -> Optional[str]:
    if bet_ratio is None or math.isinf(bet_ratio) or math.isnan(bet_ratio):
        return None
    for low, high, label in BET_BUCKETS:
        if low <= bet_ratio < high:
            return label
    return BET_BUCKETS[-1][2]


@dataclass
class HeroBetEvent:
    hand_id: str
    bet_c: int
    pot_before_c: int
    bet_ratio: Optional[float]
    bet_bucket: Optional[str]
    num_opponents: int
    success: bool
    texture: str


def load_basic_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat: Dict[str, int] = {}
    for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1"):
        hero_seat[hand_id] = seat_no

    seats_by_hand: Dict[str, set] = defaultdict(set)
    for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats"):
        seats_by_hand[hand_id].add(seat_no)

    boards: Dict[str, str] = {hand_id: board for hand_id, board in cur.execute("SELECT hand_id, board_flop FROM hands")}

    hero_cards: Dict[str, Tuple[Optional[str], Optional[str]]] = {
        hand_id: (c1, c2)
        for hand_id, c1, c2 in cur.execute(
            """
            SELECT hc.hand_id, hc.c1, hc.c2
            FROM hole_cards hc
            JOIN seats s ON s.hand_id = hc.hand_id AND s.seat_no = hc.seat_no
            WHERE s.is_hero=1
            """
        )
    }

    big_blind: Dict[str, int] = {hand_id: bb for hand_id, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb")}

    return hero_seat, seats_by_hand, boards, hero_cards, big_blind


def load_actions(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, object]]]:
    cur = conn.cursor()
    actions_by_hand: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in cur.execute(
        """
        SELECT hand_id, ordinal, street, actor_seat, action, inc_c, pot_before_c
        FROM actions
        ORDER BY hand_id, ordinal
        """
    ):
        hand_id, ordinal, street, actor_seat, action, inc_c, pot_before_c = row
        actions_by_hand[hand_id].append(
            {
                "ordinal": ordinal,
                "street": street,
                "actor_seat": actor_seat,
                "action": action,
                "inc_c": inc_c,
                "pot_before_c": pot_before_c,
            }
        )
    return actions_by_hand


def load_hero_flop_bets(conn: sqlite3.Connection) -> List[Tuple[str, int]]:
    cur = conn.cursor()
    bets: List[Tuple[str, int]] = []
    for row in cur.execute(
        """
        SELECT a.hand_id, a.ordinal
        FROM actions a
        JOIN seats s ON s.hand_id=a.hand_id AND s.seat_no=a.actor_seat AND s.is_hero=1
        WHERE a.street='flop' AND a.action IN ('bet','raise','all-in')
        ORDER BY a.hand_id, a.ordinal
        """
    ):
        bets.append((row[0], row[1]))
    return bets


def opponents_before_actions(
    hero_seat: Dict[str, int],
    seats_by_hand: Dict[str, set],
    actions_by_hand: Dict[str, List[Dict[str, object]]],
) -> Dict[Tuple[str, int], int]:
    state: Dict[Tuple[str, int], int] = {}
    for hand_id, actions in actions_by_hand.items():
        in_hand = set(seats_by_hand.get(hand_id, set()))
        all_in = set()
        hero = hero_seat.get(hand_id)
        for act in actions:
            actor = act["actor_seat"]
            opponents = 0
            if hero in in_hand:
                opponents = len([seat for seat in in_hand if seat != hero and seat not in all_in])
            else:
                opponents = len([seat for seat in in_hand if seat not in all_in])
            state[(hand_id, act["ordinal"])] = opponents
            action = act["action"]
            if action == "fold":
                in_hand.discard(actor)
                all_in.discard(actor)
            elif action == "all-in":
                all_in.add(actor)
    return state


def hero_success_map(
    hero_bets: Iterable[Tuple[str, int]],
    actions_by_hand: Dict[str, List[Dict[str, object]]],
) -> Dict[Tuple[str, int], bool]:
    bets_set = set(hero_bets)
    success: Dict[Tuple[str, int], bool] = {}
    for hand_id, actions in actions_by_hand.items():
        for idx, act in enumerate(actions):
            key = (hand_id, act["ordinal"])
            if key not in bets_set or act["street"] != "flop":
                continue
            ok = True
            for later in actions[idx + 1 :]:
                if later["street"] != "flop":
                    break
                if later["actor_seat"] == act["actor_seat"]:
                    continue
                if later["action"] in {"call", "bet", "raise", "all-in"}:
                    ok = False
                    break
            success[key] = ok
    return success


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        hero_seat, seats_by_hand, boards, hero_cards, big_blind = load_basic_maps(conn)
        actions_by_hand = load_actions(conn)
        hero_bets = load_hero_flop_bets(conn)
        opponents_state = opponents_before_actions(hero_seat, seats_by_hand, actions_by_hand)
        success_state = hero_success_map(hero_bets, actions_by_hand)

        events: List[HeroBetEvent] = []

        for hand_id, ordinal in hero_bets:
            board_text = boards.get(hand_id)
            hero_card_tuple = hero_cards.get(hand_id)
            if not board_text or not hero_card_tuple or not hero_card_tuple[0] or not hero_card_tuple[1]:
                continue
            board_cards = parse_cards(board_text)
            hero_cards_parsed = [c for c in (parse_card(hero_card_tuple[0]), parse_card(hero_card_tuple[1])) if c]
            if len(board_cards) < 3 or len(hero_cards_parsed) < 2:
                continue
            if not hero_has_air(hero_cards_parsed, board_cards):
                continue

            actions = actions_by_hand[hand_id]
            act = next((a for a in actions if a["ordinal"] == ordinal), None)
            if not act:
                continue
            pot_before = act["pot_before_c"] or 0
            bet_c = act["inc_c"] or 0
            if pot_before <= 0 or bet_c <= 0:
                continue
            bb_c = big_blind.get(hand_id)
            bet_ratio = bet_c / pot_before if pot_before else None
            bucket = bucketize(bet_ratio)
            opponents = opponents_state.get((hand_id, ordinal), 0)
            if opponents <= 0:
                continue
            success = success_state.get((hand_id, ordinal))
            if success is None:
                # Default to failure if we cannot determine, to stay conservative
                success = False
            texture = board_texture(board_cards)
            events.append(
                HeroBetEvent(
                    hand_id=hand_id,
                    bet_c=bet_c,
                    pot_before_c=pot_before,
                    bet_ratio=bet_ratio,
                    bet_bucket=bucket,
                    num_opponents=opponents,
                    success=success,
                    texture=texture,
                )
            )

        if not events:
            print("No qualifying hero flop bets with air found.")
            return

        total = len(events)
        success_total = sum(1 for e in events if e.success)
        print(f"Total hero flop air bets: {total}")
        print(f"Success rate: {success_total/total:.3f}")

        by_bucket: Dict[str, Counter] = defaultdict(Counter)
        for e in events:
            if not e.bet_bucket:
                continue
            by_bucket[e.bet_bucket]["attempts"] += 1
            if e.success:
                by_bucket[e.bet_bucket]["success"] += 1
        print("\nSuccess by bet-size bucket:")
        for label in [b[2] for b in BET_BUCKETS]:
            data = by_bucket.get(label)
            if not data or data["attempts"] < 5:
                continue
            rate = data["success"] / data["attempts"]
            print(f"  {label:>7}: {data['attempts']:4d} attempts, {rate:.3f} success")

        by_texture: Dict[str, Counter] = defaultdict(Counter)
        for e in events:
            by_texture[e.texture]["attempts"] += 1
            if e.success:
                by_texture[e.texture]["success"] += 1
        print("\nSuccess by board texture:")
        for texture, counts in sorted(by_texture.items(), key=lambda kv: -kv[1]["attempts"]):
            if counts["attempts"] < 5:
                continue
            rate = counts["success"] / counts["attempts"]
            print(f"  {texture:<18} {counts['attempts']:4d} attempts, {rate:.3f} success")

        by_opponents: Dict[int, Counter] = defaultdict(Counter)
        for e in events:
            by_opponents[e.num_opponents]["attempts"] += 1
            if e.success:
                by_opponents[e.num_opponents]["success"] += 1
        print("\nSuccess by active opponents:")
        for opps in sorted(by_opponents):
            counts = by_opponents[opps]
            rate = counts["success"] / counts["attempts"]
            print(f"  {opps} opp(s): {counts['attempts']:4d} attempts, {rate:.3f} success")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
