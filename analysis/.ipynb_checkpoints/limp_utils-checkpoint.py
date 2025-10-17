from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

RANK_TO_VALUE: Dict[str, int] = {
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

VALUE_TO_RANK: Dict[int, str] = {value: rank for rank, value in RANK_TO_VALUE.items()}
SUITS = {"C", "D", "H", "S"}


def _normalise_card(token: Optional[str]) -> Optional[Tuple[str, str]]:
    if not token:
        return None
    cleaned = token.strip().upper()
    if len(cleaned) < 2:
        return None
    suit = cleaned[0]
    rank_part = cleaned[1:]
    if rank_part.startswith("10"):
        rank = "T"
    else:
        rank = rank_part[0]
    if suit not in SUITS or rank not in RANK_TO_VALUE:
        return None
    return suit, rank


def _hand_group(hi_rank: str, lo_rank: str, suited: bool, gap: int) -> str:
    if hi_rank == lo_rank:
        return "Pocket Pair"

    hi_val = RANK_TO_VALUE[hi_rank]
    lo_val = RANK_TO_VALUE[lo_rank]

    if suited:
        if hi_rank == "A":
            return "Suited Ax"
        if hi_val >= 11 and lo_val >= 10:
            return "Suited Broadways"
        if gap == 1:
            return "Suited Connector"
        if gap == 2:
            return "Suited 1-Gapper"
        if gap == 3:
            return "Suited 2-Gapper"
        return "Other Suited"

    if hi_rank == "A":
        if lo_val >= 10:
            return "Offsuit Broadways"
        return "Offsuit Ax"
    if hi_val >= 11 and lo_val >= 10:
        return "Offsuit Broadways"
    if gap == 1:
        return "Offsuit Connector"
    if gap == 2:
        return "Offsuit 1-Gapper"
    return "Other Offsuit"


def classify_preflop_hand(c1: str, c2: str) -> Optional[Dict[str, object]]:
    card1 = _normalise_card(c1)
    card2 = _normalise_card(c2)
    if not card1 or not card2:
        return None

    suit1, rank1 = card1
    suit2, rank2 = card2
    value1 = RANK_TO_VALUE[rank1]
    value2 = RANK_TO_VALUE[rank2]

    if value1 < value2:
        suit1, suit2 = suit2, suit1
        rank1, rank2 = rank2, rank1
        value1, value2 = value2, value1

    suited = suit1 == suit2

    if rank1 == rank2:
        label = f"{rank1}{rank1}"
        gap = 0
        group = "Pocket Pair"
    else:
        suffix = "s" if suited else "o"
        label = f"{rank1}{rank2}{suffix}"
        gap = value1 - value2
        group = _hand_group(rank1, rank2, suited, gap)

    return {
        "label": label,
        "group": group,
        "suited": suited,
        "gap": gap,
        "hi_rank": rank1,
        "lo_rank": rank2,
        "hi_value": value1,
        "lo_value": value2,
    }


def _process_hand(
    hand_id: str,
    actions: List[sqlite3.Row],
    seat_info: Dict[Tuple[str, int], Dict[str, object]],
    hole_cards: Dict[Tuple[str, int], Dict[str, object]],
    seat_counts: Dict[str, Optional[int]],
) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    raise_seen = False
    limper_count = 0
    prior_actions: List[str] = []

    for row in actions:
        seat_no = row["actor_seat"]
        action = (row["action"] or "").lower()

        if seat_no is None or not action:
            continue

        if action in {"post", "ante", "blind"}:
            continue

        if action == "fold":
            prior_actions.append("fold")
            continue

        if action in {"raise", "bet", "all-in"}:
            raise_seen = True
            break

        if action == "call" and not raise_seen:
            info = seat_info.get((hand_id, seat_no))
            limpers_before = limper_count
            limper_count += 1

            only_blinds = False
            if info and (info.get("position") == "SB") and all(a == "fold" for a in prior_actions):
                only_blinds = True

            prior_actions.append("call")

            if not info or info.get("is_hero"):
                continue

            cards = hole_cards.get((hand_id, seat_no))
            if not cards:
                continue

            events.append(
                {
                    "hand_id": hand_id,
                    "seat_no": int(seat_no),
                    "position_pre": info.get("position") or "Unknown",
                    "limp_order": limper_count,
                    "limpers_before": limpers_before,
                    "limp_type": "open" if limpers_before == 0 else "over",
                    "only_blinds": only_blinds,
                    "table_seats": seat_counts.get(hand_id),
                    "c1": cards["c1"],
                    "c2": cards["c2"],
                    "cards_shown": bool(cards.get("shown")),
                    "cards_mucked": bool(cards.get("mucked")),
                }
            )
            continue

        prior_actions.append(action)

    return events


def load_limp_events(
    db_path: Path,
    *,
    cache_path: Optional[Path] = None,
    force: bool = False,
) -> List[Dict[str, object]]:
    if cache_path and cache_path.exists() and not force:
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached:
            return cached

    events: List[Dict[str, object]] = []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        seat_info: Dict[Tuple[str, int], Dict[str, object]] = {}
        for row in conn.execute(
            "SELECT hand_id, seat_no, position_pre, is_hero FROM seats"
        ):
            seat_info[(row["hand_id"], row["seat_no"])] = {
                "position": row["position_pre"],
                "is_hero": bool(row["is_hero"]),
            }

        seat_counts = {
            row["hand_id"]: row["seat_count_start"]
            for row in conn.execute("SELECT hand_id, seat_count_start FROM hands")
        }

        hole_cards: Dict[Tuple[str, int], Dict[str, object]] = {}
        for row in conn.execute(
            "SELECT hand_id, seat_no, c1, c2, shown, mucked FROM hole_cards"
        ):
            c1 = (row["c1"] or "").strip().upper()
            c2 = (row["c2"] or "").strip().upper()
            if not c1 or not c2:
                continue
            hole_cards[(row["hand_id"], row["seat_no"])] = {
                "c1": c1,
                "c2": c2,
                "shown": row["shown"],
                "mucked": row["mucked"],
            }

        cur = conn.execute(
            """
            SELECT hand_id, ordinal, actor_seat, action, inc_c, to_amount_c
            FROM actions
            WHERE street='preflop'
            ORDER BY hand_id, ordinal
            """
        )

        current_hand: Optional[str] = None
        buffer: List[sqlite3.Row] = []

        for row in cur:
            hand_id = row["hand_id"]
            if current_hand is not None and hand_id != current_hand:
                events.extend(_process_hand(current_hand, buffer, seat_info, hole_cards, seat_counts))
                buffer = []
            current_hand = hand_id
            buffer.append(row)

        if current_hand is not None and buffer:
            events.extend(_process_hand(current_hand, buffer, seat_info, hole_cards, seat_counts))

    finally:
        conn.close()

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(events, fh, ensure_ascii=False, indent=2)

    return events


__all__ = ["classify_preflop_hand", "load_limp_events"]

