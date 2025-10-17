#!/usr/bin/env python3
"""Analyse SB open sizing (blind-vs-blind) for all players and hero."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

SIZE_BUCKETS: Sequence[tuple[float, float, str]] = (
    (2.0, 2.3, "2.0-2.3x"),
    (2.3, 2.6, "2.3-2.6x"),
    (2.6, 3.0, "2.6-3.0x"),
    (3.0, 3.5, "3.0-3.5x"),
    (3.5, 4.0, "3.5-4.0x"),
    (4.0, math.inf, "4.0x+")
)


@dataclass
class OpenAttempt:
    hand_id: str
    is_hero: bool
    size_bb: float
    bucket: Optional[str]
    success: bool  # BB folded preflop


def load_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {hand_id: seat_no for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    positions = {(hand_id, seat_no): pos for hand_id, seat_no, pos in cur.execute("SELECT hand_id, seat_no, position_pre FROM seats")}
    bb_map = {hand_id: bb for hand_id, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb") if bb}
    return hero_seat, positions, bb_map


def load_preflop_actions(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, int]]]:
    cur = conn.cursor()
    actions: Dict[str, List[Dict[str, int]]] = defaultdict(list)
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


def analyse_open(
    hand_id: str,
    hero_seat: Dict[str, int],
    positions: Dict[tuple[str, int], str],
    bb_map: Dict[str, int],
    actions: List[Dict[str, int]],
) -> Optional[OpenAttempt]:
    bb = bb_map.get(hand_id)
    if not bb:
        return None
    first_idx = None
    for idx, act in enumerate(actions):
        action = act["action"]
        seat = act["seat"]
        pos = positions.get((hand_id, seat))
        if action == "post":
            continue
        if pos != "SB":
            # players before SB must fold to give us BvB
            if action != "fold":
                return None
            continue
        # pos == SB
        first_idx = idx
        break

    if first_idx is None:
        return None

    first = actions[first_idx]
    if first["action"] not in ("raise", "bet", "all-in"):
        return None

    size = first["to"] / bb if bb else 0
    if size <= 0:
        return None

    success = True
    for later in actions[first_idx + 1 :]:
        if later["action"] in ("call", "raise", "all-in", "bet"):
            success = False
            break

    return OpenAttempt(
        hand_id=hand_id,
        is_hero=(hero_seat.get(hand_id) == first["seat"]),
        size_bb=size,
        bucket=bucketize(size),
        success=success,
    )


def summarize(title: str, attempts: List[OpenAttempt]) -> None:
    if not attempts:
        print(f"{title}: no data\n")
        return
    avg_size = sum(a.size_bb for a in attempts) / len(attempts)
    success_rate = sum(1 for a in attempts if a.success) / len(attempts)
    print(f"{title}")
    print(f"  Opens:   {len(attempts)}")
    print(f"  Avg size {avg_size:.2f}x")
    print(f"  Success  {success_rate*100:.2f}%\n")

    buckets = defaultdict(Counter)
    size_counter = Counter(round(a.size_bb, 2) for a in attempts)
    for att in attempts:
        label = att.bucket or "other"
        buckets[label]["opps"] += 1
        if att.success:
            buckets[label]["success"] += 1
    print("  Bucket breakdown:")
    print(f"    {'Bucket':<10}{'Opens':>6}{'Succ%':>8}")
    for _, _, label in SIZE_BUCKETS:
        data = buckets.get(label)
        if not data:
            continue
        rate = data["success"] / data["opps"] if data["opps"] else 0
        print(f"    {label:<10}{data['opps']:6d}{rate*100:8.2f}")
    if "other" in buckets:
        data = buckets["other"]
        rate = data["success"] / data["opps"] if data["opps"] else 0
        print(f"    {'other':<10}{data['opps']:6d}{rate*100:8.2f}")

    print("\n  Top exact sizes:")
    for size, count in size_counter.most_common(5):
        succ = sum(1 for a in attempts if round(a.size_bb, 2) == size and a.success)
        rate = succ / count if count else 0
        print(f"    {size:>4.2f}x : {count:4d} opens, {rate*100:6.2f}% success")
    print()


def hero_opportunity_stats(
    hero_seat: Dict[str, int],
    positions: Dict[tuple[str, int], str],
    actions_map: Dict[str, List[Dict[str, int]]]
) -> tuple[int, int, int]:
    """Return (opportunities, opens, folds) for hero SB when folded to."""
    opportunities = opens = folds = 0
    for hand_id, seat in hero_seat.items():
        if positions.get((hand_id, seat)) != "SB":
            continue
        actions = actions_map.get(hand_id)
        if not actions:
            continue
        first_idx = None
        for idx, act in enumerate(actions):
            action = act["action"]
            pos = positions.get((hand_id, act["seat"]))
            if action == "post":
                continue
            if pos != "SB":
                if action != "fold":
                    first_idx = None
                    break
                continue
            first_idx = idx
            break
        if first_idx is None:
            continue
        opportunities += 1
        first = actions[first_idx]
        if first["action"] in ("raise", "bet", "all-in"):
            opens += 1
        else:
            folds += 1
    return opportunities, opens, folds


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, positions, bb_map = load_maps(conn)
        actions = load_preflop_actions(conn)

        attempts: List[OpenAttempt] = []
        for hand_id, acts in actions.items():
            attempt = analyse_open(hand_id, hero_seat, positions, bb_map, acts)
            if attempt:
                attempts.append(attempt)

        hero_attempts = [a for a in attempts if a.is_hero]
        population_attempts = [a for a in attempts if not a.is_hero]

        summarize("Hero SB opens (BvB)", hero_attempts)
        summarize("Population SB opens (BvB)", population_attempts)

        opps, opens, folds = hero_opportunity_stats(hero_seat, positions, actions)
        if opps:
            print(f"Hero opportunities: {opps}, opens: {opens} ({opens/opps*100:.2f}%), checks/folds: {folds}")
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
