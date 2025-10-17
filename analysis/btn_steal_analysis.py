#!/usr/bin/env python3
"""Analyse button steal sizing and success for all players (including hero)."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

BET_BUCKETS: Sequence[Tuple[float, float, str]] = (
    (1.5, 2.0, "1.5-2.0x"),
    (2.0, 2.2, "2.0-2.2x"),
    (2.2, 2.5, "2.2-2.5x"),
    (2.5, 2.7, "2.5-2.7x"),
    (2.7, 3.0, "2.7-3.0x"),
    (3.0, math.inf, "3.0x+")
)


@dataclass
class StealAttempt:
    hand_id: str
    is_hero: bool
    size_bb: float
    bucket: Optional[str]
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
        SELECT hand_id, ordinal, actor_seat, action, inc_c, to_amount_c, info
        FROM actions
        WHERE street='preflop'
        ORDER BY hand_id, ordinal
        """
    ):
        hand_id, ordinal, actor_seat, action, inc_c, to_amount_c, info = row
        actions[hand_id].append(
            {
                "ordinal": ordinal,
                "seat": actor_seat,
                "action": action,
                "inc": inc_c or 0,
                "to": to_amount_c or 0,
                "info": info,
            }
        )
    return actions


def bucketize(size_bb: float) -> Optional[str]:
    for low, high, label in BET_BUCKETS:
        if low <= size_bb < high:
            return label
    return None


def is_straddled(actions: List[Dict[str, object]], bb_c: int, positions: Dict[int, str]) -> bool:
    for act in actions:
        if act["action"] != "post":
            continue
        seat = act["seat"]
        pos = positions.get(seat)
        if pos not in ("SB", "BB") and (act["to"] or act["inc"]) and (act["to"] or 0) > bb_c:
            return True
    return False


def analyse_hand(
    hand_id: str,
    hero_seat: Dict[str, int],
    positions_map: Dict[Tuple[str, int], str],
    bb_map: Dict[str, int],
    actions: List[Dict[str, object]],
) -> Optional[StealAttempt]:
    bb_c = bb_map.get(hand_id)
    if not bb_c:
        return None
    seat_positions_local = {seat: positions_map.get((hand_id, seat)) for seat in {a["seat"] for a in actions}}
    if is_straddled(actions, bb_c, seat_positions_local):
        return None

    first_raise_idx = None
    for idx, act in enumerate(actions):
        if act["action"] in ("raise", "all-in"):
            first_raise_idx = idx
            break
        if act["action"] in ("bet",):
            first_raise_idx = idx
            break
    if first_raise_idx is None:
        return None

    first_act = actions[first_raise_idx]
    seat = first_act["seat"]
    position = seat_positions_local.get(seat)
    if position != "BTN":
        return None

    # ensure no limpers or raises before BTN acts (excluding folds and posts)
    for prior in actions[:first_raise_idx]:
        if prior["action"] in ("post", "check"):
            continue
        if prior["action"] != "fold":
            return None

    size_to = first_act["to"]
    if size_to <= 0:
        return None
    size_bb = size_to / bb_c
    if size_bb < 1.5:
        return None

    # determine success: no calls/raises afterwards
    success = True
    for later in actions[first_raise_idx + 1 :]:
        later_action = later["action"]
        if later_action in ("call", "raise", "all-in", "bet"):
            success = False
            break
    bucket = bucketize(size_bb)
    is_hero = hero_seat.get(hand_id) == seat
    return StealAttempt(hand_id=hand_id, is_hero=is_hero, size_bb=size_bb, bucket=bucket, success=success)


def summarize(attempts: List[StealAttempt], title: str) -> None:
    if not attempts:
        print(f"{title}: no data\n")
        return
    avg_size = sum(a.size_bb for a in attempts) / len(attempts)
    success_rate = sum(1 for a in attempts if a.success) / len(attempts)
    print(f"{title}")
    print(f"  Attempts: {len(attempts)}")
    print(f"  Avg Size: {avg_size:.2f}x")
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
    for _, _, label in BET_BUCKETS:
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


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, positions, bb_map = load_maps(conn)
        preflop_actions = load_preflop_actions(conn)
        attempts: List[StealAttempt] = []
        for hand_id, actions in preflop_actions.items():
            attempt = analyse_hand(hand_id, hero_seat, positions, bb_map, actions)
            if attempt:
                attempts.append(attempt)

        hero_attempts = [a for a in attempts if a.is_hero]
        population_attempts = [a for a in attempts if not a.is_hero]

        summarize(hero_attempts, "Hero BTN steal sizing")
        summarize(population_attempts, "Population BTN steal sizing")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
