#!/usr/bin/env python3
"""Report hero squeeze tendencies vs. population baselines."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"


@dataclass
class Opportunity:
    hand_id: str
    seat_no: int
    position: Optional[str]
    bb_c: Optional[int]
    is_hero: bool
    attempted: bool
    success: bool


def load_base_maps(conn: sqlite3.Connection):
    cur = conn.cursor()
    hero_seat = {hand_id: seat_no for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats WHERE is_hero=1")}
    seat_positions: Dict[Tuple[str, int], str] = {
        (hand_id, seat_no): pos
        for hand_id, seat_no, pos in cur.execute("SELECT hand_id, seat_no, position_pre FROM seats")
    }
    bb_map = {hand_id: bb for hand_id, bb in cur.execute("SELECT hand_id, bb_c FROM v_hand_bb")}
    seats_by_hand: Dict[str, List[int]] = defaultdict(list)
    for hand_id, seat_no in cur.execute("SELECT hand_id, seat_no FROM seats"):
        seats_by_hand[hand_id].append(seat_no)
    return hero_seat, seat_positions, bb_map, seats_by_hand


def load_preflop_actions(conn: sqlite3.Connection) -> Dict[str, List[Tuple[int, int, str]]]:
    cur = conn.cursor()
    actions: Dict[str, List[Tuple[int, int, str]]] = defaultdict(list)
    for hand_id, ordinal, actor_seat, action in cur.execute(
        """
        SELECT hand_id, ordinal, actor_seat, action
        FROM actions
        WHERE street='preflop'
        ORDER BY hand_id, ordinal
        """
    ):
        actions[hand_id].append((ordinal, actor_seat, action))
    return actions


def analyse_hand(
    hand_id: str,
    hero_seat: Dict[str, int],
    seat_positions: Dict[Tuple[str, int], str],
    bb_map: Dict[str, int],
    actions: List[Tuple[int, int, str]],
) -> List[Opportunity]:
    opportunities: List[Opportunity] = []
    last_raise_actor: Optional[int] = None
    callers_since_raise: List[int] = []
    recorded: Dict[int, bool] = {}
    bb_c = bb_map.get(hand_id)
    hero = hero_seat.get(hand_id)

    for idx, (ordinal, actor, action) in enumerate(actions):
        if action in {"post", "check"}:
            continue
        squeeze_context = last_raise_actor is not None and callers_since_raise and actor != last_raise_actor
        if squeeze_context and not recorded.get(actor):
            # Record opportunity on first decision in squeeze context
            attempted = action in {"raise", "all-in"}
            success = False
            if attempted:
                success = True
                for later in actions[idx + 1 :]:
                    later_actor = later[1]
                    later_action = later[2]
                    if later_action in {"raise", "all-in", "call"} and later_actor != actor:
                        success = False
                        break
            opportunities.append(
                Opportunity(
                    hand_id=hand_id,
                    seat_no=actor,
                    position=seat_positions.get((hand_id, actor)),
                    bb_c=bb_c,
                    is_hero=(actor == hero),
                    attempted=attempted,
                    success=success,
                )
            )
            recorded[actor] = True
        if action in {"raise", "bet", "all-in"}:
            last_raise_actor = actor
            callers_since_raise = []
        elif action == "call" and last_raise_actor is not None:
            callers_since_raise.append(actor)
        elif action == "fold" and actor in callers_since_raise:
            callers_since_raise = [c for c in callers_since_raise if c != actor]
    return opportunities


def aggregate(opportunities: List[Opportunity]):
    hero_pos = defaultdict(lambda: {"opps": 0, "attempts": 0, "success": 0})
    pop_pos = defaultdict(lambda: {"opps": 0, "attempts": 0, "success": 0})
    hero_stake = defaultdict(lambda: {"opps": 0, "attempts": 0, "success": 0})
    pop_stake = defaultdict(lambda: {"opps": 0, "attempts": 0, "success": 0})

    for opp in opportunities:
        if not opp.position:
            continue
        target_pos = hero_pos if opp.is_hero else pop_pos
        target_stake = hero_stake if opp.is_hero else pop_stake
        target_pos[opp.position]["opps"] += 1
        target_pos[opp.position]["attempts"] += int(opp.attempted)
        target_pos[opp.position]["success"] += int(opp.success)
        if opp.bb_c is not None:
            target_stake[opp.bb_c]["opps"] += 1
            target_stake[opp.bb_c]["attempts"] += int(opp.attempted)
            target_stake[opp.bb_c]["success"] += int(opp.success)
    return hero_pos, pop_pos, hero_stake, pop_stake


def print_section(title: str, data: Dict, success: bool = True) -> None:
    print(title)
    print(f"{'Key':<8}{'Opps':>8}{'Att':>8}{'Rate%':>8}{'Succ%':>8}")
    for key in sorted(data):
        stats = data[key]
        opps = stats["opps"]
        if opps == 0:
            continue
        attempts = stats["attempts"]
        rate = 100.0 * attempts / opps
        if success and attempts > 0:
            succ_rate = 100.0 * stats["success"] / attempts
        else:
            succ_rate = 0.0
        key_label = str(key)
        print(f"{key_label:<8}{opps:8d}{attempts:8d}{rate:8.2f}{succ_rate:8.2f}")
    print()


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")
        hero_seat, seat_positions, bb_map, _ = load_base_maps(conn)
        preflop_actions = load_preflop_actions(conn)
        all_opps: List[Opportunity] = []
        for hand_id, actions in preflop_actions.items():
            all_opps.extend(analyse_hand(hand_id, hero_seat, seat_positions, bb_map, actions))

        hero_pos, pop_pos, hero_stake, pop_stake = aggregate(all_opps)
        print_section("Hero squeeze by position:", hero_pos)
        print_section("Population squeeze by position:", pop_pos)
        print_section("Hero squeeze by stake:", hero_stake)
        print_section("Population squeeze by stake:", pop_stake)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
