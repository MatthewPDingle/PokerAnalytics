#!/usr/bin/env python3
"""Analyse BB raises over limpers (iso) for the entire population."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

SIZE_BUCKETS: Sequence[Tuple[float, float, str]] = (
    (2.5, 3.0, "2.5-3.0x"),
    (3.0, 3.5, "3.0-3.5x"),
    (3.5, 4.0, "3.5-4.0x"),
    (4.0, 5.0, "4.0-5.0x"),
    (5.0, 6.0, "5.0-6.0x"),
    (6.0, math.inf, "6.0x+")
)


@dataclass
class IsoAttempt:
    hand_id: str
    is_hero: bool
    size_bb: float
    bucket: Optional[str]
    limpers: int
    success: bool


def load_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {hand_id: seat_no for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    positions = {(hand_id, seat_no): pos for hand_id, seat_no, pos in cur.execute("SELECT hand_id, seat_no, position_pre FROM seats")}
    bb_map = {hand_id: bb for hand_id, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb") if bb}
    return hero_seat, positions, bb_map


def load_preflop_actions(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, object]]]:
    cur = conn.cursor()
    actions: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in cur.execute(
        """
        SELECT hand_id, ordinal, actor_seat, action, inc_c, to_amount_c
        FROM actions
        WHERE street='preflop'
        ORDER BY hand_id, ordinal
        """
    ):
        hand_id, ordinal, actor_seat, action, inc_c, to_amount_c = row
        actions[hand_id].append(
            {
                "ordinal": ordinal,
                "seat": actor_seat,
                "action": action,
                "inc": inc_c or 0,
                "to": to_amount_c or 0,
            }
        )
    return actions


def bucketize(size_bb: float) -> Optional[str]:
    for low, high, label in SIZE_BUCKETS:
        if low <= size_bb < high:
            return label
    return None


def analyse_hand(
    hand_id: str,
    hero_seat: Dict[str, int],
    positions: Dict[Tuple[str, int], str],
    bb_map: Dict[str, int],
    actions: List[Dict[str, object]],
) -> Optional[IsoAttempt]:
    bb_c = bb_map.get(hand_id)
    if not bb_c:
        return None
    seat_positions = {seat: positions.get((hand_id, seat)) for seat in {a["seat"] for a in actions}}

    first_raise_idx = None
    for idx, act in enumerate(actions):
        if act["action"] in ("raise", "bet", "all-in"):
            first_raise_idx = idx
            break
    if first_raise_idx is None:
        return None

    raiser = actions[first_raise_idx]
    seat = raiser["seat"]
    if seat_positions.get(seat) != "BB":
        return None

    limpers = 0
    for act in actions[:first_raise_idx]:
        if act["action"] in ("raise", "bet", "all-in"):
            return None
        if act["action"] == "call":
            limpers += 1
    if limpers == 0:
        return None

    size_to = raiser["to"]
    if size_to <= 0:
        return None
    size_bb = size_to / bb_c
    bucket = bucketize(size_bb)

    success = True
    for later in actions[first_raise_idx + 1 :]:
        if later["action"] in ("call", "raise", "all-in", "bet"):
            success = False
            break

    return IsoAttempt(
        hand_id=hand_id,
        is_hero=(hero_seat.get(hand_id) == seat),
        size_bb=size_bb,
        bucket=bucket,
        limpers=limpers,
        success=success,
    )


def summarize(title: str, attempts: List[IsoAttempt]) -> None:
    if not attempts:
        print(f"{title}: no data\n")
        return
    avg_size = sum(a.size_bb for a in attempts) / len(attempts)
    success_rate = sum(1 for a in attempts if a.success) / len(attempts)
    avg_limpers = sum(a.limpers for a in attempts) / len(attempts)
    print(f"{title}")
    print(f"  Attempts: {len(attempts)}")
    print(f"  Avg size: {avg_size:.2f}x")
    print(f"  Avg limpers: {avg_limpers:.2f}")
    print(f"  Success:  {success_rate*100:.2f}%\n")

    buckets = defaultdict(Counter)
    size_counter = Counter(round(a.size_bb, 2) for a in attempts)
    for att in attempts:
        label = att.bucket or "other"
        buckets[label]["attempts"] += 1
        if att.success:
            buckets[label]["success"] += 1
    print("  Bucket breakdown:")
    print(f"    {'Bucket':<10}{'Att':>6}{'Succ%':>8}")
    for low, high, label in SIZE_BUCKETS:
        data = buckets.get(label)
        if not data:
            continue
        rate = data["success"] / data["attempts"] if data["attempts"] else 0
        print(f"    {label:<10}{data['attempts']:6d}{rate*100:8.2f}")
    if buckets.get("other"):
        data = buckets["other"]
        rate = data["success"] / data["attempts"] if data["attempts"] else 0
        print(f"    {'other':<10}{data['attempts']:6d}{rate*100:8.2f}")

    top_sizes = size_counter.most_common(5)
    print("\n  Top exact sizes:")
    for size, count in top_sizes:
        succ = sum(1 for a in attempts if round(a.size_bb, 2) == size and a.success)
        rate = succ / count if count else 0
        print(f"    {size:>4.2f}x : {count:4d} attempts, {rate*100:6.2f}% success")
    print()


def filter_by_limpers(attempts: List[IsoAttempt], min_limpers: int, max_limpers: Optional[int] = None) -> List[IsoAttempt]:
    result: List[IsoAttempt] = []
    for att in attempts:
        if att.limpers < min_limpers:
            continue
        if max_limpers is not None and att.limpers > max_limpers:
            continue
        result.append(att)
    return result


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, positions, bb_map = load_maps(conn)
        preflop_actions = load_preflop_actions(conn)
        attempts: List[IsoAttempt] = []
        for hand_id, actions in preflop_actions.items():
            attempt = analyse_hand(hand_id, hero_seat, positions, bb_map, actions)
            if attempt:
                attempts.append(attempt)

        hero_attempts = [a for a in attempts if a.is_hero]
        population_attempts = [a for a in attempts if not a.is_hero]

        summarize("Hero BB iso raises", hero_attempts)
        summarize("Population BB iso raises", population_attempts)

        summarize("Hero BB iso raises (1 limper)", filter_by_limpers(hero_attempts, 1, 1))
        summarize("Hero BB iso raises (>=2 limpers)", filter_by_limpers(hero_attempts, 2, None))

        summarize("Population BB iso raises (1 limper)", filter_by_limpers(population_attempts, 1, 1))
        summarize("Population BB iso raises (>=2 limpers)", filter_by_limpers(population_attempts, 2, None))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
