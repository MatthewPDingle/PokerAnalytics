#!/usr/bin/env python3
"""Analyse BB responses vs BTN opens: population sizing and fold/call/raise rates."""

from __future__ import annotations

import sqlite3
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"


@dataclass
class OpenEvent:
    hand_id: str
    actor_seat: int
    bb_seat: int
    size_bb: float
    bb_action: str  # fold/call/raise


SIZE_BUCKETS = [
    (2.0, 2.3, "2.0-2.3x"),
    (2.3, 2.6, "2.3-2.6x"),
    (2.6, 3.0, "2.6-3.0x"),
    (3.0, 3.5, "3.0-3.5x"),
    (3.5, 4.0, "3.5-4.0x"),
    (4.0, 4.5, "4.0-4.5x"),
    (4.5, 5.5, "4.5-5.5x"),
    (5.5, 7.0, "5.5-7.0x"),
    (7.0, float("inf"), "7.0x+")
]


def bucketize(size: float) -> str:
    for low, high, label in SIZE_BUCKETS:
        if low <= size < high:
            return label
    return "other"


def load_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {hand_id: seat_no for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    positions = {(hand_id, seat_no): pos for hand_id, seat_no, pos in cur.execute("SELECT hand_id, seat_no, position_pre FROM seats")}
    bb_map = {hand_id: bb for hand_id, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb") if bb}
    return hero_seat, positions, bb_map


def load_preflop_actions(conn: sqlite3.Connection) -> Dict[str, List[Tuple[int, str, int, int]]]:
    cur = conn.cursor()
    actions = defaultdict(list)
    for hand_id, ordinal, seat_no, action, inc_c, to_c in cur.execute(
        "SELECT hand_id, ordinal, actor_seat, action, inc_c, to_amount_c FROM actions WHERE street='preflop' ORDER BY hand_id, ordinal"
    ):
        actions[hand_id].append((seat_no, action, inc_c or 0, to_c or 0))
    return actions


def identify_btn_opens(hero_seat, positions, bb_map, actions_map) -> List[OpenEvent]:
    events = []
    for hand_id, acts in actions_map.items():
        bb = bb_map.get(hand_id)
        if not bb:
            continue
        btn_seat = bb_seat = None
        for seat_no, action, inc, to in acts:
            pos = positions.get((hand_id, seat_no))
            if pos == "BTN" and btn_seat is None:
                btn_seat = seat_no
            if pos == "BB" and bb_seat is None:
                bb_seat = seat_no
        if btn_seat is None or bb_seat is None:
            continue

        first_idx = None
        for idx, (seat_no, action, inc, to) in enumerate(acts):
            if action == "post":
                continue
            pos = positions.get((hand_id, seat_no))
            if pos != "BTN":
                if action != "fold":
                    first_idx = None
                    break
                continue
            first_idx = idx
            break
        if first_idx is None:
            continue

        seat_no, action, inc, to = acts[first_idx]
        if action not in ("raise", "bet", "all-in"):
            continue
        size = to / bb if bb else 0
        if size <= 0:
            continue

        bb_action = "fold"
        for seat2, action2, inc2, to2 in acts[first_idx + 1 :]:
            if seat2 != bb_seat:
                continue
            if action2 in ("fold",):
                bb_action = "fold"
            elif action2 in ("call", "check"):
                bb_action = "call"
            elif action2 in ("raise", "bet", "all-in"):
                bb_action = "raise"
            break

        events.append(OpenEvent(hand_id, seat_no, bb_seat, size, bb_action))
    return events


def summarize_population(events: List[OpenEvent], hero_seat: Dict[str, int]):
    pop_events = [e for e in events if hero_seat.get(e.hand_id) != e.actor_seat]
    total = len(pop_events)
    if not total:
        print("No BTN opens found")
        return

    print(f"Population BTN opens (folded to BTN): {total}")
    avg_size = sum(e.size_bb for e in pop_events) / total
    print(f"  Avg size: {avg_size:.2f}x")

    action_counts = Counter(e.bb_action for e in pop_events)
    for action, cnt in action_counts.items():
        print(f"  BB {action:<5}: {cnt:4d} ({cnt/total*100:5.2f}%)")

    print("\n  By size bucket (BB responses):")
    print(f"    {'Bucket':<10}{'Opens':>6}{'Fold%':>8}{'Call%':>8}{'Raise%':>8}")
    bucket_counts: Dict[str, Counter] = defaultdict(Counter)
    for e in pop_events:
        bucket_counts[bucketize(e.size_bb)][e.bb_action] += 1
    for low, high, label in SIZE_BUCKETS:
        counts = bucket_counts.get(label)
        if not counts:
            continue
        total_bucket = sum(counts.values())
        fold_pct = counts['fold']/total_bucket*100 if total_bucket else 0
        call_pct = counts['call']/total_bucket*100 if total_bucket else 0
        raise_pct = counts['raise']/total_bucket*100 if total_bucket else 0
        print(f"    {label:<10}{total_bucket:6d}{fold_pct:8.2f}{call_pct:8.2f}{raise_pct:8.2f}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, positions, bb_map = load_maps(conn)
        actions = load_preflop_actions(conn)
        events = identify_btn_opens(hero_seat, positions, bb_map, actions)
        print(f"Total BTN openings found: {len(events)}")
        summarize_population(events, hero_seat)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
