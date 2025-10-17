#!/usr/bin/env python3
"""Analyse LJ (UTG in 6-max) open sizing and downstream responses."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

SIZE_BUCKETS = [
    (2.0, 2.5, "2.0-2.49x"),
    (2.5, 3.0, "2.5-2.99x"),
    (3.0, 3.5, "3.0-3.49x"),
    (3.5, 4.0, "3.5-3.99x"),
    (4.0, 5.0, "4.0-4.99x"),
    (5.0, float("inf"), "5.0x+")
]

RESPONSE_LABELS = ["fold_out", "call", "raise"]


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


def analyse(hero_seat, positions, bb_map, actions_map):
    events = []
    for hand_id, acts in actions_map.items():
        bb = bb_map.get(hand_id)
        if not bb:
            continue
        lj_seat = None
        for seat_no in {seat for seat, _, _, _ in acts}:
            if positions.get((hand_id, seat_no)) == "UTG":
                lj_seat = seat_no
                break
        if lj_seat is None:
            continue

        # Ensure first acting seat is LJ and no limpers before
        first_idx = None
        for idx, (seat_no, action, inc, to) in enumerate(acts):
            if action == "post":
                continue
            pos = positions.get((hand_id, seat_no))
            if pos != "UTG":
                # players before LJ should fold only (i.e., none before LJ)
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

        # Determine aggregate response after LJ open
        fold_out = True
        saw_call = False
        saw_raise = False
        for seat2, action2, inc2, to2 in acts[first_idx + 1 :]:
            if action2 in ("fold", "post"):
                continue
            if action2 in ("call", "check"):
                fold_out = False
                saw_call = True
                break
            if action2 in ("raise", "bet", "all-in"):
                fold_out = False
                saw_raise = True
                break
        if fold_out:
            response = "fold_out"
        elif saw_raise:
            response = "raise"
        else:
            response = "call"

        hero_flag = hero_seat.get(hand_id) == seat_no
        events.append((hero_flag, size, response))
    return events


def summarize(events):
    hero_events = [e for e in events if e[0]]
    pop_events = events  # include hero events in population totals

    def _summary(label, data):
        if not data:
            print(f"{label}: no data")
            return
        sizes = [e[1] for e in data]
        responses = Counter(e[2] for e in data)
        print(f"{label}: {len(data)} opens")
        print(f"  Avg size: {sum(sizes)/len(sizes):.2f}x")
        for resp in RESPONSE_LABELS:
            cnt = responses.get(resp, 0)
            print(f"  {resp:8s}: {cnt:4d} ({cnt/len(data)*100:5.2f}%)")
        buckets = defaultdict(Counter)
        for _, size, resp in data:
            buckets[bucketize(size)][resp] += 1
        print("\n  By size bucket:")
        print(f"    {'Bucket':<9}{'Opens':>6}{'Fold%':>8}{'Call%':>8}{'Raise%':>8}")
        for low, high, label_b in SIZE_BUCKETS:
            counts = buckets.get(label_b)
            if not counts:
                continue
            total = sum(counts.values())
            fold_pct = counts['fold_out']/total*100 if total else 0
            call_pct = counts['call']/total*100 if total else 0
            raise_pct = counts['raise']/total*100 if total else 0
            print(f"    {label_b:<9}{total:6d}{fold_pct:8.2f}{call_pct:8.2f}{raise_pct:8.2f}")
        print()

    _summary("Hero LJ opens", hero_events)
    _summary("Population LJ opens", pop_events)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, positions, bb_map = load_maps(conn)
        actions = load_preflop_actions(conn)
        events = analyse(hero_seat, positions, bb_map, actions)
        print(f"Total LJ opens captured: {len(events)}")
        summarize(events)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
