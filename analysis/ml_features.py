#!/usr/bin/env python3
"""Build per-player feature datasets for ML modelling.

Generates one row per opponent with preflop/postflop tendencies, sample
counts, and outcome metrics derived from the warehouse.*

* Works for PokerStars-style hand histories where `seats.role_pre` stores the
  player screen name. Ignition data (anonymous seats) will produce aggregated
  position buckets until hero tagging is added.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "warehouse" / "stars.sqlite"
DEFAULT_OUT = PROJECT_ROOT / "analysis" / "features" / "players.csv"

VOLUNTARY_ACTIONS = {"call", "bet", "raise", "all-in"}
RAISE_ACTIONS = {"bet", "raise", "all-in"}
BET_ACTIONS = {"bet", "all-in"}
STEAL_POSITIONS = {"CO", "BTN", "SB"}

POSITION_COLUMNS = {
    "UTG": "hands_utg",
    "UTG+1": "hands_utg1",
    "UTG+2": "hands_utg2",
    "LJ": "hands_lj",
    "HJ": "hands_hj",
    "CO": "hands_co",
    "BTN": "hands_btn",
    "SB": "hands_sb",
    "BB": "hands_bb",
    "STRADDLE": "hands_straddle",
}


@dataclass
class PlayerAccumulator:
    hands: int = 0
    position_counts: Counter = field(default_factory=Counter)
    stack_bb_sum: float = 0.0
    stack_samples: int = 0
    rake_bb_sum: float = 0.0
    vpip_count: int = 0
    vpip_opps: int = 0
    pfr_count: int = 0
    three_bet_count: int = 0
    three_bet_opps: int = 0
    four_bet_count: int = 0
    four_bet_opps: int = 0
    cold_call_count: int = 0
    cold_call_opps: int = 0
    steal_attempts: int = 0
    steal_success: int = 0
    steal_opps: int = 0
    squeeze_count: int = 0
    squeeze_opps: int = 0
    fold_to_3bet_count: int = 0
    fold_to_3bet_opps: int = 0
    fold_to_4bet_count: int = 0
    fold_to_4bet_opps: int = 0
    cbet_flop_count: int = 0
    cbet_flop_opps: int = 0
    cbet_turn_count: int = 0
    cbet_turn_opps: int = 0
    cbet_river_count: int = 0
    cbet_river_opps: int = 0
    fold_to_cbet_flop_count: int = 0
    fold_to_cbet_flop_opps: int = 0
    fold_to_cbet_turn_count: int = 0
    fold_to_cbet_turn_opps: int = 0
    fold_to_cbet_river_count: int = 0
    fold_to_cbet_river_opps: int = 0
    aggression_bets: int = 0
    aggression_calls: int = 0
    flop_seen: int = 0
    multiway_flops: int = 0
    headsup_flops: int = 0
    wwsf_wins: int = 0
    wtsd_count: int = 0
    wsd_wins: int = 0
    net_c: int = 0
    net_bb: float = 0.0


@dataclass
class HandInfo:
    hand_id: str
    rake_c: int
    board_flop: Optional[str]
    board_turn: Optional[str]
    board_river: Optional[str]

    @property
    def has_flop(self) -> bool:
        return bool(self.board_flop)

    @property
    def has_turn(self) -> bool:
        return bool(self.board_turn)

    @property
    def has_river(self) -> bool:
        return bool(self.board_river)


@dataclass
class SeatInfo:
    player_id: str
    position: Optional[str]
    stack_start_c: Optional[int]


@dataclass
class Action:
    hand_id: str
    ordinal: int
    street: str
    seat: Optional[int]
    action: str
    info: Optional[str]
    size_c: Optional[int]
    to_amount_c: Optional[int]
    inc_c: Optional[int]


@dataclass
class Result:
    net_c: int
    showdown: int


def load_actions(conn: sqlite3.Connection) -> Dict[str, List[Action]]:
    actions: Dict[str, List[Action]] = defaultdict(list)
    cur = conn.cursor()

    has_inc = bool(
        cur.execute(
            "SELECT 1 FROM pragma_table_info('actions') WHERE name='inc_c'"
        ).fetchone()
    )

    columns = [
        "hand_id",
        "ordinal",
        "street",
        "actor_seat",
        "action",
        "info",
        "size_c",
        "to_amount_c",
    ]
    if has_inc:
        columns.append("inc_c")

    cur.execute(
        f"SELECT {', '.join(columns)} FROM actions ORDER BY hand_id, ordinal"
    )
    rows = cur.fetchall()
    idx = {name: pos for pos, name in enumerate(columns)}
    for row in rows:
        actions[row[idx["hand_id"]]].append(
            Action(
                hand_id=row[idx["hand_id"]],
                ordinal=row[idx["ordinal"]],
                street=row[idx["street"]],
                seat=row[idx["actor_seat"]],
                action=row[idx["action"]],
                info=row[idx["info"]],
                size_c=row[idx["size_c"]],
                to_amount_c=row[idx["to_amount_c"]],
                inc_c=row[idx["inc_c"]] if has_inc else None,
            )
        )
    return actions


def load_seats(conn: sqlite3.Connection) -> Dict[str, Dict[int, SeatInfo]]:
    seats: Dict[str, Dict[int, SeatInfo]] = defaultdict(dict)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT hand_id, seat_no, role_pre, position_pre, stack_start_c
        FROM seats
        """
    )
    for row in cur.fetchall():
        hand_id, seat_no, role_pre, position_pre, stack_start_c = row
        seats[hand_id][seat_no] = SeatInfo(
            player_id=role_pre,
            position=position_pre,
            stack_start_c=stack_start_c,
        )
    return seats


def load_results(conn: sqlite3.Connection) -> Dict[str, Dict[int, Result]]:
    results: Dict[str, Dict[int, Result]] = defaultdict(dict)
    cur = conn.cursor()
    cur.execute("SELECT hand_id, seat_no, net_c, COALESCE(showdown, 0) FROM results")
    for hand_id, seat_no, net_c, showdown in cur.fetchall():
        results[hand_id][seat_no] = Result(net_c=net_c or 0, showdown=int(showdown or 0))
    return results


def load_hands(conn: sqlite3.Connection) -> Dict[str, HandInfo]:
    meta: Dict[str, HandInfo] = {}
    cur = conn.cursor()
    cur.execute(
        """
        SELECT hand_id, COALESCE(rake_c, 0), board_flop, board_turn, board_river
        FROM hands
        """
    )
    for row in cur.fetchall():
        meta[row[0]] = HandInfo(
            hand_id=row[0],
            rake_c=row[1],
            board_flop=row[2],
            board_turn=row[3],
            board_river=row[4],
        )
    return meta


def detect_big_blind(actions: Sequence[Action]) -> Optional[int]:
    bb_candidates: List[int] = []
    fallback: List[int] = []
    for act in actions:
        if act.street != "preflop" or act.action != "post":
            continue
        size = act.size_c or 0
        fallback.append(size)
        info = (act.info or "").lower()
        if "straddle" in info:
            continue
        if "bb" in info or "big blind" in info:
            bb_candidates.append(size)
    if bb_candidates:
        return max(bb_candidates)
    if fallback:
        return max(fallback)
    return None


def default_state() -> Dict[str, Any]:
    return {
        "vpip": False,
        "pfr": False,
        "three_bet": False,
        "three_bet_opportunity": False,
        "four_bet": False,
        "four_bet_opportunity": False,
        "cold_call": False,
        "cold_call_opportunity": False,
        "steal_opportunity": False,
        "steal_attempt": False,
        "steal_success": False,
        "squeeze": False,
        "squeeze_opportunity": False,
        "fold_to_3bet": False,
        "fold_to_3bet_opportunity": False,
        "fold_to_4bet": False,
        "fold_to_4bet_opportunity": False,
        "folded_preflop": False,
        "flop_cbet_attempted": False,
        "flop_cbet_made": False,
        "turn_cbet_made": False,
        "saw_flop": False,
    }


def evaluate_fold_response(
    seat: int,
    player_actions: List[Dict[str, Any]],
    global_actions: List[Dict[str, Any]],
    raise_condition,
    reraised_condition,
) -> Tuple[bool, bool]:
    for act in player_actions:
        if raise_condition(act):
            for gact in global_actions[act["idx"] + 1 :]:
                if gact["seat"] == seat:
                    continue
                if not reraised_condition(gact):
                    continue
                for reply in player_actions:
                    if reply["idx"] > gact["idx"]:
                        if reply["action"] == "fold":
                            return True, True
                        if reply["action"] in VOLUNTARY_ACTIONS:
                            return False, True
                        return False, True
                return False, True
            return False, False
    return False, False


def analyse_preflop(
    preflop_actions: Sequence[Action],
    seats: Dict[int, SeatInfo],
) -> Tuple[Dict[int, Dict[str, Any]], Optional[int], List[int]]:
    states: Dict[int, Dict[str, Any]] = {seat_no: default_state() for seat_no in seats}
    player_actions: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    global_actions: List[Dict[str, Any]] = []

    raise_count = 0
    voluntary_count = 0
    calls_since_last_raise = 0
    last_aggressor: Optional[int] = None

    for act in preflop_actions:
        if act.seat is None:
            continue
        move = act.action
        seat = act.seat
        if seat not in seats:
            continue
        if move in {"post", "return"}:
            continue
        entry = {
            "idx": len(global_actions),
            "seat": seat,
            "action": move,
            "raises_before": raise_count,
            "voluntary_before": voluntary_count,
            "calls_since_last_raise": calls_since_last_raise,
        }
        global_actions.append(entry)
        player_actions[seat].append(entry)

        if move in VOLUNTARY_ACTIONS:
            states[seat]["vpip"] = True
        if move in RAISE_ACTIONS:
            states[seat]["pfr"] = True
            if entry["raises_before"] == 1:
                states[seat]["three_bet"] = True
            if entry["raises_before"] >= 2:
                states[seat]["four_bet"] = True
            if entry["raises_before"] == 1 and entry["calls_since_last_raise"] > 0:
                states[seat]["squeeze"] = True
            last_aggressor = seat
            raise_count += 1
            calls_since_last_raise = 0
        elif move == "call":
            calls_since_last_raise += 1

        if move in VOLUNTARY_ACTIONS:
            voluntary_count += 1
        if move == "fold":
            states[seat]["folded_preflop"] = True

    for seat, seat_info in seats.items():
        actions = player_actions.get(seat, [])
        state = states[seat]
        state["three_bet_opportunity"] = any(a["raises_before"] >= 1 for a in actions)
        state["four_bet_opportunity"] = any(a["raises_before"] >= 2 for a in actions)
        state["cold_call_opportunity"] = state["three_bet_opportunity"]
        state["cold_call"] = any(
            a["action"] == "call"
            and a["raises_before"] >= 1
            and not any(x["action"] in RAISE_ACTIONS for x in actions if x["idx"] < a["idx"])
            for a in actions
        )
        state["squeeze_opportunity"] = any(
            a["raises_before"] >= 1 and a["calls_since_last_raise"] > 0 for a in actions
        )

        fold_to_3bet, opp3 = evaluate_fold_response(
            seat,
            actions,
            global_actions,
            lambda a: a["action"] in RAISE_ACTIONS and a["raises_before"] == 0,
            lambda ga: ga["action"] in RAISE_ACTIONS and ga["raises_before"] >= 1,
        )
        state["fold_to_3bet"] = fold_to_3bet
        state["fold_to_3bet_opportunity"] = opp3

        fold_to_4bet, opp4 = evaluate_fold_response(
            seat,
            actions,
            global_actions,
            lambda a: a["action"] in RAISE_ACTIONS and a["raises_before"] == 1,
            lambda ga: ga["action"] in RAISE_ACTIONS and ga["raises_before"] >= 2,
        )
        state["fold_to_4bet"] = fold_to_4bet
        state["fold_to_4bet_opportunity"] = opp4

        first_action = actions[0] if actions else None
        pos = (seat_info.position or "").upper()
        if pos in STEAL_POSITIONS and first_action and first_action["raises_before"] == 0 and first_action["voluntary_before"] == 0:
            state["steal_opportunity"] = True
            if first_action["action"] in RAISE_ACTIONS:
                state["steal_attempt"] = True
                state["steal_success"] = not any(
                    ga["seat"] != seat
                    and ga["idx"] > first_action["idx"]
                    and ga["action"] in VOLUNTARY_ACTIONS
                    for ga in global_actions
                )
        elif pos in STEAL_POSITIONS and not actions:
            # Player folded without acting (sitting out) – treat as no opportunity.
            state["steal_opportunity"] = False

    active_seats = [seat for seat, st in states.items() if not st.get("folded_preflop")]
    return states, last_aggressor, active_seats


def process_flop(
    street_actions: Sequence[Action],
    active: Iterable[int],
    stats: Dict[str, PlayerAccumulator],
    seats: Dict[int, SeatInfo],
    player_states: Dict[int, Dict[str, Any]],
    last_aggressor: Optional[int],
) -> List[int]:
    active_set = set(active)
    if not street_actions:
        return list(active_set)

    actions_by_seat: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for idx, act in enumerate(street_actions):
        if act.seat is None:
            continue
        actions_by_seat[act.seat].append({"idx": idx, "action": act.action})

    cbet_idx: Optional[int] = None
    if last_aggressor is not None and last_aggressor in active_set:
        seat_actions = actions_by_seat.get(last_aggressor)
        if seat_actions:
            acc = stats[seats[last_aggressor].player_id]
            acc.cbet_flop_opps += 1
            player_states[last_aggressor]["flop_cbet_attempted"] = True
            first_action = seat_actions[0]
            if first_action["action"] in BET_ACTIONS:
                acc.cbet_flop_count += 1
                player_states[last_aggressor]["flop_cbet_made"] = True
                cbet_idx = first_action["idx"]
            else:
                player_states[last_aggressor]["flop_cbet_made"] = False
        else:
            player_states[last_aggressor]["flop_cbet_attempted"] = False
            player_states[last_aggressor]["flop_cbet_made"] = False

    if cbet_idx is not None:
        for seat in list(active_set):
            if seat == last_aggressor:
                continue
            seat_actions = actions_by_seat.get(seat)
            if not seat_actions:
                continue
            response = next((a for a in seat_actions if a["idx"] > cbet_idx), None)
            if response is None:
                continue
            acc = stats[seats[seat].player_id]
            acc.fold_to_cbet_flop_opps += 1
            if response["action"] == "fold":
                acc.fold_to_cbet_flop_count += 1

    for act in street_actions:
        seat = act.seat
        if seat not in active_set:
            continue
        move = act.action
        if move in {"post", "return"}:
            continue
        acc = stats[seats[seat].player_id]
        if move in BET_ACTIONS or move == "raise":
            acc.aggression_bets += 1
        elif move == "call":
            acc.aggression_calls += 1
        if move == "fold":
            active_set.discard(seat)

    return list(active_set)


def process_barrel(
    street_actions: Sequence[Action],
    active: Iterable[int],
    stats: Dict[str, PlayerAccumulator],
    seats: Dict[int, SeatInfo],
    player_states: Dict[int, Dict[str, Any]],
    last_aggressor: Optional[int],
    prev_cbet_flag: str,
    made_flag: str,
    count_attr: str,
    opp_attr: str,
    fold_count_attr: str,
    fold_opp_attr: str,
) -> List[int]:
    active_set = set(active)
    if not street_actions:
        return list(active_set)

    actions_by_seat: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for idx, act in enumerate(street_actions):
        if act.seat is None:
            continue
        actions_by_seat[act.seat].append({"idx": idx, "action": act.action})

    cbet_idx: Optional[int] = None
    if (
        last_aggressor is not None
        and last_aggressor in active_set
        and player_states[last_aggressor].get(prev_cbet_flag)
    ):
        seat_actions = actions_by_seat.get(last_aggressor)
        if seat_actions:
            acc = stats[seats[last_aggressor].player_id]
            setattr(acc, opp_attr, getattr(acc, opp_attr) + 1)
            first_action = seat_actions[0]
            if first_action["action"] in BET_ACTIONS:
                setattr(acc, count_attr, getattr(acc, count_attr) + 1)
                player_states[last_aggressor][made_flag] = True
                cbet_idx = first_action["idx"]
            else:
                player_states[last_aggressor][made_flag] = False
        else:
            player_states[last_aggressor][made_flag] = False
    elif last_aggressor is not None:
        player_states[last_aggressor][made_flag] = False

    if cbet_idx is not None:
        for seat in list(active_set):
            if seat == last_aggressor:
                continue
            seat_actions = actions_by_seat.get(seat)
            if not seat_actions:
                continue
            response = next((a for a in seat_actions if a["idx"] > cbet_idx), None)
            if response is None:
                continue
            acc = stats[seats[seat].player_id]
            setattr(acc, fold_opp_attr, getattr(acc, fold_opp_attr) + 1)
            if response["action"] == "fold":
                setattr(acc, fold_count_attr, getattr(acc, fold_count_attr) + 1)

    for act in street_actions:
        seat = act.seat
        if seat not in active_set:
            continue
        move = act.action
        if move in {"post", "return"}:
            continue
        acc = stats[seats[seat].player_id]
        if move in BET_ACTIONS or move == "raise":
            acc.aggression_bets += 1
        elif move == "call":
            acc.aggression_calls += 1
        if move == "fold":
            active_set.discard(seat)

    return list(active_set)


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def round2(value: float) -> float:
    return round(value, 2)


def build_rows(stats: Dict[str, PlayerAccumulator], min_hands: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for player_id, acc in stats.items():
        if acc.hands < min_hands:
            continue
        row: Dict[str, Any] = {}
        row["player_id"] = player_id
        row["hands_total"] = acc.hands
        for pos, column in POSITION_COLUMNS.items():
            row[column] = acc.position_counts.get(pos, 0)
        other_positions = sum(
            count for pos, count in acc.position_counts.items() if pos not in POSITION_COLUMNS
        )
        row["hands_other_position"] = other_positions

        avg_stack_bb = safe_div(acc.stack_bb_sum, acc.stack_samples)
        row["avg_stack_bb"] = round2(avg_stack_bb)

        row["net_bb_total"] = round(acc.net_bb, 3)
        row["bb_per_100"] = round2(100.0 * safe_div(acc.net_bb, acc.hands))
        row["rake_bb_per_100"] = round2(100.0 * safe_div(acc.rake_bb_sum, acc.hands))

        row["vpip_count"] = acc.vpip_count
        row["vpip_opps"] = acc.vpip_opps
        row["vpip_pct"] = pct(acc.vpip_count, acc.vpip_opps)

        row["pfr_count"] = acc.pfr_count
        row["pfr_pct"] = pct(acc.pfr_count, acc.vpip_opps)
        row["vpip_pfr_gap_pct"] = round2(row["vpip_pct"] - row["pfr_pct"])

        row["three_bet_count"] = acc.three_bet_count
        row["three_bet_opps"] = acc.three_bet_opps
        row["three_bet_pct"] = pct(acc.three_bet_count, acc.three_bet_opps)

        row["four_bet_count"] = acc.four_bet_count
        row["four_bet_opps"] = acc.four_bet_opps
        row["four_bet_pct"] = pct(acc.four_bet_count, acc.four_bet_opps)

        row["cold_call_count"] = acc.cold_call_count
        row["cold_call_opps"] = acc.cold_call_opps
        row["cold_call_pct"] = pct(acc.cold_call_count, acc.cold_call_opps)

        row["steal_attempts"] = acc.steal_attempts
        row["steal_opps"] = acc.steal_opps
        row["steal_attempt_pct"] = pct(acc.steal_attempts, acc.steal_opps)
        row["steal_success"] = acc.steal_success
        row["steal_success_pct"] = pct(acc.steal_success, acc.steal_attempts)

        row["squeeze_count"] = acc.squeeze_count
        row["squeeze_opps"] = acc.squeeze_opps
        row["squeeze_pct"] = pct(acc.squeeze_count, acc.squeeze_opps)

        row["fold_to_3bet_count"] = acc.fold_to_3bet_count
        row["fold_to_3bet_opps"] = acc.fold_to_3bet_opps
        row["fold_to_3bet_pct"] = pct(acc.fold_to_3bet_count, acc.fold_to_3bet_opps)

        row["fold_to_4bet_count"] = acc.fold_to_4bet_count
        row["fold_to_4bet_opps"] = acc.fold_to_4bet_opps
        row["fold_to_4bet_pct"] = pct(acc.fold_to_4bet_count, acc.fold_to_4bet_opps)

        row["cbet_flop_count"] = acc.cbet_flop_count
        row["cbet_flop_opps"] = acc.cbet_flop_opps
        row["cbet_flop_pct"] = pct(acc.cbet_flop_count, acc.cbet_flop_opps)

        row["cbet_turn_count"] = acc.cbet_turn_count
        row["cbet_turn_opps"] = acc.cbet_turn_opps
        row["cbet_turn_pct"] = pct(acc.cbet_turn_count, acc.cbet_turn_opps)

        row["cbet_river_count"] = acc.cbet_river_count
        row["cbet_river_opps"] = acc.cbet_river_opps
        row["cbet_river_pct"] = pct(acc.cbet_river_count, acc.cbet_river_opps)

        row["fold_to_cbet_flop_count"] = acc.fold_to_cbet_flop_count
        row["fold_to_cbet_flop_opps"] = acc.fold_to_cbet_flop_opps
        row["fold_to_cbet_flop_pct"] = pct(acc.fold_to_cbet_flop_count, acc.fold_to_cbet_flop_opps)

        row["fold_to_cbet_turn_count"] = acc.fold_to_cbet_turn_count
        row["fold_to_cbet_turn_opps"] = acc.fold_to_cbet_turn_opps
        row["fold_to_cbet_turn_pct"] = pct(acc.fold_to_cbet_turn_count, acc.fold_to_cbet_turn_opps)

        row["fold_to_cbet_river_count"] = acc.fold_to_cbet_river_count
        row["fold_to_cbet_river_opps"] = acc.fold_to_cbet_river_opps
        row["fold_to_cbet_river_pct"] = pct(acc.fold_to_cbet_river_count, acc.fold_to_cbet_river_opps)

        bets = acc.aggression_bets
        calls = acc.aggression_calls
        row["aggression_bets"] = bets
        row["aggression_calls"] = calls
        row["aggression_frequency"] = round2(safe_div(bets, bets + calls))

        row["flop_seen"] = acc.flop_seen
        row["multiway_flops"] = acc.multiway_flops
        row["headsup_flops"] = acc.headsup_flops
        row["multiway_flop_pct"] = pct(acc.multiway_flops, acc.flop_seen)

        row["wwsf_wins"] = acc.wwsf_wins
        row["wwsf_pct"] = pct(acc.wwsf_wins, acc.flop_seen)

        row["wtsd_count"] = acc.wtsd_count
        row["wtsd_pct"] = pct(acc.wtsd_count, acc.flop_seen)

        row["wsd_wins"] = acc.wsd_wins
        row["wsd_pct"] = pct(acc.wsd_wins, acc.wtsd_count)

        rows.append(row)

    rows.sort(key=lambda r: r["player_id"].lower())
    return rows


def generate_features(conn: sqlite3.Connection, min_hands: int = 2000) -> List[Dict[str, Any]]:
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-200000;")
    conn.row_factory = sqlite3.Row
    actions_map = load_actions(conn)
    seats_map = load_seats(conn)
    results_map = load_results(conn)
    hands_map = load_hands(conn)

    stats: Dict[str, PlayerAccumulator] = defaultdict(PlayerAccumulator)

    hand_ids = sorted(hands_map.keys())
    for hand_id in hand_ids:
        seats = seats_map.get(hand_id)
        if not seats:
            continue
        actions = actions_map.get(hand_id, [])
        bb_c = detect_big_blind(actions)
        if not bb_c or bb_c == 0:
            continue

        hand_info = hands_map[hand_id]
        preflop_actions = [a for a in actions if a.street == "preflop"]
        player_states, last_aggressor, active_seats = analyse_preflop(preflop_actions, seats)

        for seat_no, seat in seats.items():
            player_id = seat.player_id
            acc = stats[player_id]
            acc.hands += 1
            if seat.position:
                acc.position_counts[seat.position] += 1
            if seat.stack_start_c:
                acc.stack_bb_sum += seat.stack_start_c / bb_c
                acc.stack_samples += 1
            acc.rake_bb_sum += hand_info.rake_c / bb_c
            acc.vpip_opps += 1

            state = player_states.get(seat_no, default_state())
            if state["vpip"]:
                acc.vpip_count += 1
            if state["pfr"]:
                acc.pfr_count += 1
            if state["three_bet"]:
                acc.three_bet_count += 1
            if state["three_bet_opportunity"]:
                acc.three_bet_opps += 1
            if state["four_bet"]:
                acc.four_bet_count += 1
            if state["four_bet_opportunity"]:
                acc.four_bet_opps += 1
            if state["cold_call"]:
                acc.cold_call_count += 1
            if state["cold_call_opportunity"]:
                acc.cold_call_opps += 1
            if state["steal_opportunity"]:
                acc.steal_opps += 1
            if state["steal_attempt"]:
                acc.steal_attempts += 1
            if state["steal_success"]:
                acc.steal_success += 1
            if state["squeeze"]:
                acc.squeeze_count += 1
            if state["squeeze_opportunity"]:
                acc.squeeze_opps += 1
            if state["fold_to_3bet_opportunity"]:
                acc.fold_to_3bet_opps += 1
            if state["fold_to_3bet"]:
                acc.fold_to_3bet_count += 1
            if state["fold_to_4bet_opportunity"]:
                acc.fold_to_4bet_opps += 1
            if state["fold_to_4bet"]:
                acc.fold_to_4bet_count += 1

        active_set = set(active_seats)
        if hand_info.has_flop and active_set:
            multiway = len(active_set) >= 3
            headsup = len(active_set) == 2
            for seat in list(active_set):
                player_states[seat]["saw_flop"] = True
                player_id = seats[seat].player_id
                acc = stats[player_id]
                acc.flop_seen += 1
                if multiway:
                    acc.multiway_flops += 1
                if headsup:
                    acc.headsup_flops += 1
        else:
            for seat in player_states:
                player_states[seat]["saw_flop"] = False

        flop_actions = [a for a in actions if a.street == "flop"] if hand_info.has_flop else []
        active_after_flop = process_flop(flop_actions, active_set, stats, seats, player_states, last_aggressor)

        turn_actions = (
            [a for a in actions if a.street == "turn"] if hand_info.has_turn else []
        )
        active_after_turn: List[int] = active_after_flop
        if hand_info.has_turn:
            active_after_turn = process_barrel(
                turn_actions,
                active_after_flop,
                stats,
                seats,
                player_states,
                last_aggressor,
                "flop_cbet_made",
                "turn_cbet_made",
                "cbet_turn_count",
                "cbet_turn_opps",
                "fold_to_cbet_turn_count",
                "fold_to_cbet_turn_opps",
            )

        river_actions = (
            [a for a in actions if a.street == "river"] if hand_info.has_river else []
        )
        if hand_info.has_river:
            process_barrel(
                river_actions,
                active_after_turn,
                stats,
                seats,
                player_states,
                last_aggressor,
                "turn_cbet_made",
                "river_cbet_made",
                "cbet_river_count",
                "cbet_river_opps",
                "fold_to_cbet_river_count",
                "fold_to_cbet_river_opps",
            )

        result_rows = results_map.get(hand_id, {})
        for seat_no, seat in seats.items():
            res = result_rows.get(seat_no)
            acc = stats[seat.player_id]
            if res:
                net_c = res.net_c
                acc.net_c += net_c
                acc.net_bb += safe_div(net_c, bb_c)
                if res.showdown:
                    acc.wtsd_count += 1
                    if net_c > 0:
                        acc.wsd_wins += 1
                if player_states.get(seat_no, {}).get("saw_flop") and net_c > 0:
                    acc.wwsf_wins += 1

    return build_rows(stats, min_hands)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: List[Dict[str, Any]]) -> None:
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("Parquet output requires pandas. Install pandas to enable this format.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-player ML feature dataset")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to warehouse SQLite file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output file path (csv or parquet)")
    parser.add_argument(
        "--format",
        choices=["csv", "parquet", "both"],
        default="csv",
        help="Output format (both writes CSV and Parquet)",
    )
    parser.add_argument(
        "--parquet-out",
        type=Path,
        default=None,
        help="Optional explicit Parquet path when --format both",
    )
    parser.add_argument("--min-hands", type=int, default=2000, help="Minimum hands required per player")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")
    with sqlite3.connect(args.db) as conn:
        rows = generate_features(conn, min_hands=args.min_hands)
    if args.format == "csv":
        write_csv(args.out, rows)
        print(f"Wrote {len(rows)} player rows to {args.out}")
    elif args.format == "parquet":
        write_parquet(args.out, rows)
        print(f"Wrote {len(rows)} player rows to {args.out}")
    else:  # both
        csv_path = args.out
        if csv_path.suffix == "":
            csv_path = csv_path / "players.csv"
        write_csv(csv_path, rows)
        parquet_path = args.parquet_out or csv_path.with_suffix(".parquet")
        write_parquet(parquet_path, rows)
        print(f"Wrote {len(rows)} player rows to {csv_path} and {parquet_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
