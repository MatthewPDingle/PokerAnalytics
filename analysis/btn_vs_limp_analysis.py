#!/usr/bin/env python3
"""Analyse BTN actions versus limpers ahead (no raises)."""

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


@dataclass
class IsoEvent:
    hero_event: bool
    size_bb: float
    limpers: int
    response: str  # fold_out, call, raise


def load_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {h: s for h, s in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    positions = {(h, s): pos for h, s, pos in cur.execute("SELECT hand_id, seat_no, position_pre FROM seats")}
    bb_map = {h: bb for h, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb") if bb}
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
    events: List[IsoEvent] = []
    target_pos = "BTN"
    for hand_id, acts in actions_map.items():
        bb = bb_map.get(hand_id)
        if not bb:
            continue
        btn_seat = None
        for seat in {seat for seat, _, _, _ in acts}:
            if positions.get((hand_id, seat)) == target_pos:
                btn_seat = seat
                break
        if btn_seat is None:
            continue

        limpers = 0
        first_idx = None
        for idx, (seat_no, action, inc, to) in enumerate(acts):
            if action == "post":
                continue
            pos = positions.get((hand_id, seat_no))
            if pos != target_pos:
                if action in ("fold",):
                    continue
                if action == "call":
                    limpers += 1
                    continue
                # any raise before BTN -> skip
                first_idx = None
                limpers = 0
                break
            first_idx = idx
            break
        if first_idx is None or limpers == 0:
            continue

        seat_no, action, inc, to = acts[first_idx]
        if action == "fold":
            events.append(IsoEvent(hero_seat.get(hand_id) == seat_no, 0.0, limpers, "fold"))
            continue
        if action not in ("raise", "bet", "all-in"):
            continue

        size = to / bb if bb else 0
        if size <= 0:
            continue

        response = "fold_out"
        for seat2, action2, inc2, to2 in acts[first_idx + 1 :]:
            if action2 in ("fold", "post"):
                continue
            if action2 in ("call", "check"):
                response = "call"
                break
            if action2 in ("raise", "bet", "all-in"):
                response = "raise"
                break

        events.append(IsoEvent(hero_seat.get(hand_id) == seat_no, size, limpers, response))
    return events


def summarize(events: List[IsoEvent]):
    hero_events = [e for e in events if e.hero_event]
    population = events

    def _summary(label: str, data: List[IsoEvent]):
        if not data:
            print(f"{label}: no data")
            return
        sizes = [e.size_bb for e in data if e.size_bb > 0]
        responses = Counter(e.response for e in data)
        avg_limpers = sum(e.limpers for e in data) / len(data)
        print(f"{label}: {len(data)} iso attempts")
        print(f"  Avg limpers: {avg_limpers:.2f}")
        if sizes:
            print(f"  Avg raise size: {sum(sizes)/len(sizes):.2f}x")
        for resp in ("fold_out", "call", "raise"):
            cnt = responses.get(resp, 0)
            print(f"  {resp:8s}: {cnt:4d} ({cnt/len(data)*100:5.2f}%)")

        buckets = defaultdict(Counter)
        for e in data:
            if e.size_bb > 0:
                bucket = next((label for low, high, label in SIZE_BUCKETS if low <= e.size_bb < high), "other")
                buckets[bucket][e.response] += 1

        print("\n  By size bucket:")
        print(f"    {'Limp':<4}{'Bucket':<10}{'Count':>6}{'Fold%':>8}{'Call%':>8}{'Raise%':>8}")
        for limper_count in sorted({e.limpers for e in data}):
            for low, high, label_b in SIZE_BUCKETS:
                counts = Counter()
                total = 0
                for e in data:
                    if e.limpers != limper_count or e.size_bb <= 0:
                        continue
                    bucket = next((label for low, high, label in SIZE_BUCKETS if low <= e.size_bb < high), "other")
                    if bucket != label_b:
                        continue
                    counts[e.response] += 1
                    total += 1
                if total == 0:
                    continue
                fold_pct = counts['fold_out']/total*100
                call_pct = counts['call']/total*100
                raise_pct = counts['raise']/total*100
                print(f"    {limper_count:<4}{label_b:<10}{total:6d}{fold_pct:8.2f}{call_pct:8.2f}{raise_pct:8.2f}")
        print()

    _summary("Hero BTN iso", hero_events)
    _summary("Population BTN iso", population)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero, positions, bb_map = load_maps(conn)
        actions = load_preflop_actions(conn)
        events = analyse(hero, positions, bb_map, actions)
        print(f"Total BTN iso opportunities captured: {len(events)}")
        summarize(events)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
