"""Build aggregated preflop response-curve datasets from the warehouse."""

from __future__ import annotations

import json
import math
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set

from poker_analytics.config import build_data_paths
from poker_analytics.data.bet_sizing import BET_SIZE_BUCKETS, BetSizeBucket, bucket_for_ratio
from poker_analytics.data.cards import extract_big_blind
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.db import connect_readonly
from poker_analytics.services.preflop_response_curves import (
    ResponseCurvePoint,
    ResponseCurveScenario,
    _SAMPLE_SCENARIOS,
)


# Stack-depth buckets (in big blinds) aligned with the product requirements.
@dataclass(frozen=True)
class StackBucket:
    key: str
    label: str
    lower: float
    upper: float


STACK_BUCKETS: Sequence[StackBucket] = (
    StackBucket(key="bb_0_30", label="0-30 bb", lower=0.0, upper=30.0),
    StackBucket(key="bb_30_60", label="30-60 bb", lower=30.0, upper=60.0),
    StackBucket(key="bb_60_100", label="60-100 bb", lower=60.0, upper=100.0),
    StackBucket(key="bb_100_plus", label="100+ bb", lower=100.0, upper=float("inf")),
)


@dataclass(frozen=True)
class PotBucket:
    key: str
    label: str
    lower: float
    upper: float


POT_BUCKETS: Sequence[PotBucket] = (
    PotBucket(key="pot_blinds", label="Blinds Only (~1.5 bb)", lower=0.0, upper=2.5),
    PotBucket(key="pot_small", label="2-4 bb", lower=2.5, upper=4.5),
    PotBucket(key="pot_medium", label="4-7 bb", lower=4.5, upper=7.5),
    PotBucket(key="pot_large", label="7-12 bb", lower=7.5, upper=12.5),
    PotBucket(key="pot_huge", label="12+ bb", lower=12.5, upper=float("inf")),
)


SITUATION_METADATA = {
    "folded_to_hero": "Folded to hero (no raises yet)",
    "facing_limpers": "Facing one or more limpers",
    "facing_single_raise": "Facing open raise",
    "facing_raise_with_callers": "Facing raise with callers",
    "facing_three_bet": "Facing 3-bet after raising",
}

RAISE_ACTIONS = {"raise", "bet", "all-in"}
CALL_ACTIONS = {"call"}
IGNORE_ACTIONS = {"check", "timeout"}
POST_ACTIONS = {"post"}


@dataclass
class BucketAggregate:
    count: int = 0
    fold_count: int = 0
    call_count: int = 0
    raise_count: int = 0
    pot_sum_bb: float = 0.0
    invest_sum_bb: float = 0.0
    final_pot_sum_bb: float = 0.0
    players_remaining_sum: float = 0.0

    def register(
        self,
        response: str,
        pot_before_bb: float,
        invest_bb: float,
        final_pot_bb: float,
        final_players: float,
    ) -> None:
        self.count += 1
        self.pot_sum_bb += pot_before_bb
        self.invest_sum_bb += invest_bb
        self.final_pot_sum_bb += final_pot_bb
        self.players_remaining_sum += final_players
        if response == "fold":
            self.fold_count += 1
        elif response == "call":
            self.call_count += 1
        elif response == "raise":
            self.raise_count += 1

    def to_point(self, bucket: BetSizeBucket) -> Optional[ResponseCurvePoint]:
        if self.count == 0:
            return None
        fold_pct = self.fold_count / self.count * 100.0
        call_pct = self.call_count / self.count * 100.0
        raise_pct = self.raise_count / self.count * 100.0
        avg_pot = self.pot_sum_bb / self.count if self.count else 0.0
        avg_invest = self.invest_sum_bb / self.count if self.count else 0.0

        # Simplistic expectation: hero wins the pot immediately when everyone folds
        # and invests the raise amount otherwise.
        lose_pct = (self.call_count + self.raise_count) / self.count
        ev_bb = fold_pct / 100.0 * avg_pot - lose_pct * avg_invest

        if math.isfinite(bucket.upper):
            representative_ratio = (bucket.lower + bucket.upper) / 2
        else:
            representative_ratio = bucket.lower + 0.5

        return ResponseCurvePoint(
            bucket_key=bucket.key,
            bucket_label=bucket.label,
            representative_ratio=representative_ratio,
            fold_pct=round(fold_pct, 2),
            call_pct=round(call_pct, 2),
            raise_pct=round(raise_pct, 2),
            ev_bb=round(ev_bb, 3),
            expected_final_pot_bb=round(self.final_pot_sum_bb / self.count if self.count else 0.0, 3),
            expected_players_remaining=round(
                self.players_remaining_sum / self.count if self.count else 0.0, 2
            ),
        )


@dataclass
class ScenarioAggregate:
    hero_position: str
    stack_bucket: StackBucket
    pot_bucket: PotBucket
    vpip_ahead: int
    players_behind: int
    situation_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    effective_stack_sum_bb: float = 0.0
    pot_before_sum_bb: float = 0.0
    samples: int = 0
    buckets: Dict[str, BucketAggregate] = field(default_factory=lambda: defaultdict(BucketAggregate))

    def register(
        self,
        bucket: BetSizeBucket,
        response: str,
        pot_before_bb: float,
        invest_bb: float,
        effective_stack_bb: float,
        final_pot_bb: float,
        final_players: float,
        situation_key: str,
    ) -> None:
        self.samples += 1
        self.effective_stack_sum_bb += effective_stack_bb
        self.pot_before_sum_bb += pot_before_bb
        if situation_key:
            self.situation_counts[situation_key] += 1
        self.buckets[bucket.key].register(response, pot_before_bb, invest_bb, final_pot_bb, final_players)

    def to_scenario(self) -> Optional[ResponseCurveScenario]:
        if self.samples == 0:
            return None
        points: List[ResponseCurvePoint] = []
        for bucket in BET_SIZE_BUCKETS:
            point = self.buckets.get(bucket.key)
            if not point:
                continue
            response_point = point.to_point(bucket)
            if response_point:
                points.append(response_point)
        if not points:
            return None

        pot_before_avg = self.pot_before_sum_bb / self.samples if self.samples else 0.0
        effective_stack_avg = self.effective_stack_sum_bb / self.samples if self.samples else 0.0

        primary_situation_key = ""
        if self.situation_counts:
            primary_situation_key = max(self.situation_counts, key=self.situation_counts.get)
        primary_situation_label = _map_situation_label(primary_situation_key) if primary_situation_key else ""

        scenario_id = "_".join(
            [
                self.hero_position.lower(),
                self.stack_bucket.key,
                self.pot_bucket.key,
                f"vpip{self.vpip_ahead}",
                f"behind{self.players_behind}",
            ]
        )

        return ResponseCurveScenario(
            id=scenario_id,
            hero_position=self.hero_position,
            villain_profile="Population",
            stack_bucket_key=self.stack_bucket.key,
            stack_depth=self.stack_bucket.label,
            situation_key=primary_situation_key,
            situation_label=primary_situation_label,
            vpip_ahead=self.vpip_ahead,
            players_behind=self.players_behind,
            pot_bucket_key=self.pot_bucket.key,
            pot_bucket=self.pot_bucket.label,
            pot_size_bb=round(pot_before_avg, 3),
            effective_stack_bb=round(effective_stack_avg, 3),
            sample_size=self.samples,
            points=points,
        )


def _stack_bucket_for(effective_stack_bb: float) -> Optional[StackBucket]:
    if effective_stack_bb <= 0:
        return None
    for bucket in STACK_BUCKETS:
        if effective_stack_bb < bucket.upper or math.isclose(effective_stack_bb, bucket.upper):
            if effective_stack_bb >= bucket.lower:
                return bucket
    return STACK_BUCKETS[-1]


def _pot_bucket_for(pot_before_bb: float) -> PotBucket:
    value = max(pot_before_bb, 0.0)
    for bucket in POT_BUCKETS:
        if value < bucket.upper or math.isclose(value, bucket.upper):
            if value >= bucket.lower:
                return bucket
    return POT_BUCKETS[-1]


def _situation_key(raise_count: int, calls_since_raise: int, calls_before_raise: int) -> str:
    if raise_count == 0:
        if calls_before_raise > 0:
            return "facing_limpers"
        return "folded_to_hero"
    if raise_count == 1 and calls_since_raise == 0:
        return "facing_single_raise"
    if raise_count == 1 and calls_since_raise > 0:
        return "facing_raise_with_callers"
    return "facing_three_bet"


def _map_situation_label(key: str) -> str:
    return SITUATION_METADATA.get(key, key.replace("_", " ").title())


@dataclass
class ActionRow:
    hand_id: str
    ordinal: int
    street: str
    seat_no: Optional[int]
    action: str
    inc_c: Optional[float]
    to_amount_c: Optional[float]


@dataclass
class SeatRow:
    position: Optional[str]
    stack_start_c: Optional[float]


def _load_actions(conn: sqlite3.Connection) -> Dict[str, List[ActionRow]]:
    has_inc_column = bool(
        conn.execute("SELECT 1 FROM pragma_table_info('actions') WHERE name='inc_c'").fetchone()
    )
    columns = ["hand_id", "ordinal", "street", "actor_seat", "action", "to_amount_c"]
    if has_inc_column:
        columns.append("inc_c")
    sql = (
        "SELECT "
        + ", ".join(columns)
        + " FROM actions WHERE street='preflop' ORDER BY hand_id, ordinal"
    )
    rows = conn.execute(sql)
    actions: Dict[str, List[ActionRow]] = defaultdict(list)
    for row in rows:
        data = dict(zip(columns, row))
        actions[data["hand_id"]].append(
            ActionRow(
                hand_id=data["hand_id"],
                ordinal=data["ordinal"],
                street=data["street"],
                seat_no=data.get("actor_seat"),
                action=str(data.get("action", "")).lower(),
                inc_c=data.get("inc_c"),
                to_amount_c=data.get("to_amount_c"),
            )
        )
    return actions


def _load_seats(conn: sqlite3.Connection) -> Dict[str, Dict[int, SeatRow]]:
    sql = "SELECT hand_id, seat_no, position_pre, stack_start_c FROM seats"
    seats: Dict[str, Dict[int, SeatRow]] = defaultdict(dict)
    for hand_id, seat_no, position_pre, stack_start_c in conn.execute(sql):
        seats[hand_id][seat_no] = SeatRow(
            position=position_pre,
            stack_start_c=stack_start_c,
        )
    return seats


def _load_big_blinds(conn: sqlite3.Connection) -> Dict[str, float]:
    # v_hand_bb exists in the warehouse; fall back to zero if missing.
    sql = "SELECT hand_id, bb_c FROM v_hand_bb"
    mapping: Dict[str, float] = {}
    try:
        for hand_id, bb_c in conn.execute(sql):
            if bb_c:
                mapping[hand_id] = float(bb_c)
    except sqlite3.OperationalError:
        # View not available in this warehouse snapshot.
        pass
    return mapping


def _load_big_blinds_from_hand_histories(conn: sqlite3.Connection, hand_ids: Iterable[str]) -> Dict[str, float]:
    unresolved = [hand_id for hand_id in hand_ids]
    if not unresolved:
        return {}
    mapping: Dict[str, float] = {}
    chunk_size = 500
    for start in range(0, len(unresolved), chunk_size):
        chunk = unresolved[start : start + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        query = f"SELECT HandHistoryId, HandHistory FROM HandHistories WHERE HandHistoryId IN ({placeholders})"
        try:
            rows = conn.execute(query, chunk)
        except sqlite3.OperationalError:
            break
        for hand_id, hand_history in rows:
            if not hand_history:
                continue
            try:
                root = ET.fromstring(hand_history)
            except ET.ParseError:
                continue
            bb = extract_big_blind(root)
            if bb:
                mapping[str(hand_id)] = bb
    return mapping


class ResponseCurveBuilder:
    def __init__(self) -> None:
        self._scenarios: Dict[tuple, ScenarioAggregate] = {}

    def _scenario(
        self,
        hero_position: str,
        stack_bucket: StackBucket,
        pot_bucket: PotBucket,
        vpip_ahead: int,
        players_behind: int,
    ) -> ScenarioAggregate:
        key = (hero_position, stack_bucket.key, pot_bucket.key, vpip_ahead, players_behind)
        if key not in self._scenarios:
            self._scenarios[key] = ScenarioAggregate(
                hero_position=hero_position,
                stack_bucket=stack_bucket,
                pot_bucket=pot_bucket,
                vpip_ahead=vpip_ahead,
                players_behind=players_behind,
            )
        return self._scenarios[key]

    def process_hand(
        self,
        hand_id: str,
        actions: List[ActionRow],
        seats: Dict[int, SeatRow],
        bb_c: float,
    ) -> None:
        if not actions or not seats or not bb_c:
            return

        player_contrib: Dict[int, float] = defaultdict(float)
        pot_c = 0.0
        raise_count = 0
        calls_since_raise = 0
        calls_total = 0
        vpipped_players: Set[int] = set()
        hero_events: List[HeroEvent] = []
        folded_seats: Set[int] = set()

        for idx, action in enumerate(actions):
            seat = action.seat_no
            action_name = action.action
            if seat is None:
                continue

            inc_c = action.inc_c
            if inc_c is None and action.to_amount_c is not None:
                inc_c = max(0.0, float(action.to_amount_c) - player_contrib[seat])

            if action_name in POST_ACTIONS:
                if inc_c:
                    pot_c += inc_c
                    player_contrib[seat] += inc_c
                continue

            if action_name in IGNORE_ACTIONS:
                continue

            if action_name in CALL_ACTIONS:
                if inc_c:
                    pot_c += inc_c
                    player_contrib[seat] += inc_c
                calls_since_raise += 1
                calls_total += 1
                vpipped_players.add(seat)
                continue

            if action_name == "fold":
                folded_seats.add(seat)
                continue

            if action_name in RAISE_ACTIONS:
                seat_info = seats.get(seat)
                if not seat_info or not seat_info.position:
                    # Without positional info we cannot bucket correctly.
                    if inc_c and inc_c > 0:
                        pot_c += inc_c
                        player_contrib[seat] += inc_c
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                pot_before_c = pot_c
                invest_c = inc_c or 0.0
                if invest_c <= 0:
                    if inc_c is None and action.to_amount_c is not None:
                        invest_c = max(0.0, float(action.to_amount_c) - player_contrib[seat])
                if invest_c <= 0 or pot_before_c <= 0:
                    if invest_c > 0:
                        pot_c += invest_c
                        player_contrib[seat] += invest_c
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                # Determine stack bucket.
                hero_stack_c = seat_info.stack_start_c or 0.0
                if hero_stack_c <= 0:
                    hero_stack_c = 0.0
                villain_max_stack_c = 0.0
                for seat_no, other in seats.items():
                    if seat_no == seat:
                        continue
                    stack = other.stack_start_c or 0.0
                    if stack > villain_max_stack_c:
                        villain_max_stack_c = stack
                if villain_max_stack_c <= 0:
                    villain_max_stack_c = hero_stack_c

                effective_stack_bb = 0.0
                if bb_c:
                    effective_stack_bb = min(hero_stack_c, villain_max_stack_c) / bb_c
                stack_bucket = _stack_bucket_for(effective_stack_bb)
                if not stack_bucket:
                    if invest_c > 0:
                        pot_c += invest_c
                        player_contrib[seat] += invest_c
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                ratio = invest_c / pot_before_c if pot_before_c else 0.0
                bet_bucket = bucket_for_ratio(ratio)
                if not bet_bucket:
                    if invest_c > 0:
                        pot_c += invest_c
                        player_contrib[seat] += invest_c
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                situation_key = _situation_key(raise_count, calls_since_raise, calls_total)
                response = _classify_response(actions, idx, seat)
                players_behind = _count_players_to_act(actions, idx, seat)

                pot_before_bb = pot_before_c / bb_c if bb_c else 0.0
                invest_bb = invest_c / bb_c if bb_c else 0.0

                pot_bucket = _pot_bucket_for(pot_before_bb)
                vpip_ahead = len({p for p in vpipped_players if p != seat})
                hero_events.append(
                    HeroEvent(
                        position=seat_info.position,
                        stack_bucket=stack_bucket,
                        pot_bucket=pot_bucket,
                        situation_key=situation_key,
                        bet_bucket=bet_bucket,
                        response=response,
                        pot_before_bb=pot_before_bb,
                        invest_bb=invest_bb,
                        players_behind=players_behind,
                        vpip_ahead=vpip_ahead,
                        effective_stack_bb=effective_stack_bb,
                    )
                )

                pot_c += invest_c
                player_contrib[seat] += invest_c
                raise_count += 1
                calls_since_raise = 0
                calls_total = 0
                vpipped_players.add(seat)
                continue

            # Any other action types are ignored for now.

        final_pot_bb = pot_c / bb_c if bb_c else 0.0
        remaining_players = {
            seat_no
            for seat_no, amount in player_contrib.items()
            if amount > 0 and seat_no not in folded_seats
        }
        final_players = len(remaining_players)

        for event in hero_events:
            scenario = self._scenario(
                event.position,
                event.stack_bucket,
                event.pot_bucket,
                event.vpip_ahead,
                event.players_behind,
            )
            scenario.register(
                event.bet_bucket,
                event.response,
                event.pot_before_bb,
                event.invest_bb,
                event.effective_stack_bb,
                final_pot_bb,
                final_players,
                event.situation_key,
            )

    def build(self) -> List[ResponseCurveScenario]:
        scenarios: List[ResponseCurveScenario] = []
        for aggregator in self._scenarios.values():
            scenario = aggregator.to_scenario()
            if scenario:
                scenarios.append(scenario)
        scenarios.sort(
            key=lambda s: (
                s.hero_position,
                s.stack_bucket_key,
                s.pot_bucket_key,
                s.vpip_ahead,
                s.players_behind,
            )
        )
        return scenarios


@dataclass
class ParsedAction:
    name: str
    seat: Optional[int]
    action: str  # 'fold', 'call', 'raise', 'check'
    amount: float


@dataclass
class HeroEvent:
    position: str
    stack_bucket: StackBucket
    pot_bucket: PotBucket
    situation_key: str
    bet_bucket: BetSizeBucket
    response: str
    pot_before_bb: float
    invest_bb: float
    players_behind: int
    vpip_ahead: int
    effective_stack_bb: float


def _classify_response(actions: List[ActionRow], idx: int, hero_seat: int) -> str:
    for later in actions[idx + 1 :]:
        if later.seat_no is None or later.action in POST_ACTIONS:
            continue
        if later.seat_no == hero_seat:
            break
        if later.action in IGNORE_ACTIONS:
            continue
        if later.action == "fold":
            # Continue scanning to see if someone else acts.
            continue
        if later.action in CALL_ACTIONS:
            return "call"
        if later.action in RAISE_ACTIONS:
            return "raise"
        break
    return "fold"


def _count_players_to_act(actions: List[ActionRow], idx: int, hero_seat: int) -> int:
    seats = {a.seat_no for a in actions[idx + 1 :] if a.seat_no is not None and a.seat_no != hero_seat}
    return len(seats)


def _classify_response_steps(actions: List[ParsedAction], idx: int, name: str) -> str:
    for later in actions[idx + 1 :]:
        if later.name == name:
            continue
        if later.action in {"fold", "check"}:
            continue
        if later.action == "call":
            return "call"
        if later.action == "raise":
            return "raise"
    return "fold"


def _count_players_to_act_steps(actions: List[ParsedAction], idx: int, name: str) -> int:
    return len({later.name for later in actions[idx + 1 :] if later.name != name})


POSITION_RING_MAP: Dict[int, List[str]] = {
    2: ["SB", "BB"],
    3: ["SB", "BB", "BTN"],
    4: ["SB", "BB", "CO", "BTN"],
    5: ["SB", "BB", "UTG", "CO", "BTN"],
    6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"],
    7: ["SB", "BB", "UTG", "UTG+1", "HJ", "CO", "BTN"],
    8: ["SB", "BB", "UTG", "UTG+1", "UTG+2", "HJ", "CO", "BTN"],
    9: ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN"],
}


def _parse_players(game: ET.Element) -> List[dict]:
    players_section = game.find('./general/players')
    if players_section is None:
        return []
    players: List[dict] = []
    for player in players_section.findall('player'):
        seat = player.attrib.get('seat')
        name = player.attrib.get('name')
        if not seat or not name:
            continue
        try:
            seat_int = int(seat)
        except ValueError:
            continue
        chips_text = player.attrib.get('chips') or player.attrib.get('stack')
        try:
            chips = float(chips_text) if chips_text else 0.0
        except ValueError:
            chips = 0.0
        dealer = player.attrib.get('dealer') == '1'
        players.append({'name': name, 'seat': seat_int, 'chips': chips, 'dealer': dealer})
    return players


def _find_small_blind(game: ET.Element) -> Optional[int]:
    round_zero = game.find("round[@no='0']")
    if round_zero is None:
        return None
    for action in round_zero.findall('action'):
        action_type = action.attrib.get('type')
        if action_type == '1':
            return action.attrib.get('player')
    return None


def _assign_positions_from_players(players: List[dict], sb_player_name: Optional[str]) -> Dict[str, str]:
    if not players:
        return {}
    seats_sorted = sorted(players, key=lambda p: p['seat'])
    seat_to_player = {p['seat']: p for p in seats_sorted}
    name_to_seat = {p['name']: p['seat'] for p in seats_sorted}

    if sb_player_name and sb_player_name in name_to_seat:
        sb_seat = name_to_seat[sb_player_name]
    else:
        sb_seat = seats_sorted[0]['seat']

    seat_order = [p['seat'] for p in seats_sorted]
    if sb_seat in seat_order:
        start_idx = seat_order.index(sb_seat)
    else:
        start_idx = 0
    rotation = seats_sorted[start_idx:] + seats_sorted[:start_idx]

    template = POSITION_RING_MAP.get(len(rotation))
    if not template:
        template = ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN"][: len(rotation)]

    mapping: Dict[str, str] = {}
    for player, position in zip(rotation, template):
        mapping[player['name']] = position
    return mapping


def _initial_pot_and_contrib(game: ET.Element, name_to_position: Dict[str, str]) -> tuple[float, Dict[str, float]]:
    pot = 0.0
    contrib: Dict[str, float] = defaultdict(float)
    round_zero = game.find("round[@no='0']")
    if round_zero is not None:
        for action in round_zero.findall('action'):
            name = action.attrib.get('player')
            if not name or name not in name_to_position:
                continue
            try:
                amount = float(action.attrib.get('sum') or 0.0)
            except ValueError:
                amount = 0.0
            if amount > 0:
                pot += amount
                contrib[name] += amount
    return pot, contrib


def _parse_preflop_actions(game: ET.Element, name_to_position: Dict[str, str]) -> List[ParsedAction]:
    preflop = game.find("round[@no='1']")
    if preflop is None:
        return []
    steps: List[ParsedAction] = []
    for action in preflop.findall('action'):
        name = action.attrib.get('player')
        if not name or name not in name_to_position:
            continue
        action_type = action.attrib.get('type')
        try:
            amount = float(action.attrib.get('sum') or 0.0)
        except ValueError:
            amount = 0.0
        if action_type in {'0'}:
            steps.append(ParsedAction(name=name, seat=None, action='fold', amount=amount))
        elif action_type in {'3'}:
            steps.append(ParsedAction(name=name, seat=None, action='call', amount=amount))
        elif action_type in {'4'}:
            steps.append(ParsedAction(name=name, seat=None, action='check', amount=amount))
        elif action_type in {'23', '7'}:
            steps.append(ParsedAction(name=name, seat=None, action='raise', amount=amount))
        else:
            continue
    return steps


def build_response_curves(max_hands: Optional[int] = None) -> List[ResponseCurveScenario]:
    """Extract response-curve scenarios from the DriveHUD warehouse.

    If the warehouse is unavailable the function returns an empty list so callers
    can fall back to synthetic data.
    """

    data_paths = build_data_paths()
    if not data_paths.drivehud_db.exists():
        return []

    seats_map: Dict[str, Dict[int, SeatRow]] = {}
    bb_map: Dict[str, float] = {}

    with connect_readonly(data_paths.drivehud_db) as conn:
        try:
            actions_map = _load_actions(conn)
        except sqlite3.OperationalError:
            actions_map = None
        if actions_map:
            seats_map = _load_seats(conn)
            bb_map = _load_big_blinds(conn)
            missing_bb = [hand_id for hand_id in actions_map if hand_id not in bb_map]
            if missing_bb:
                extra_bb = _load_big_blinds_from_hand_histories(conn, missing_bb)
                bb_map.update(extra_bb)

    if actions_map:
        builder = ResponseCurveBuilder()
        counter = 0
        for hand_id, action_rows in actions_map.items():
            if max_hands is not None and counter >= max_hands:
                break
            seats = seats_map.get(hand_id)
            bb_value = bb_map.get(hand_id)
            if not seats or not bb_value:
                continue
            builder.process_hand(hand_id, action_rows, seats, bb_value)
            counter += 1
        scenarios = builder.build()
        if scenarios:
            return scenarios

    # Fallback: parse XML hand histories directly when warehouse tables are
    # unavailable (common for DriveHUD exports).
    return _build_from_hand_histories(max_hands)


def _build_from_hand_histories(max_hands: Optional[int]) -> List[ResponseCurveScenario]:
    source = DriveHudDataSource.from_defaults()
    if not source.is_available():
        return []

    builder = ResponseCurveBuilder()
    processed = 0

    query = "SELECT HandHistoryId, HandHistory FROM HandHistories ORDER BY HandHistoryId"
    for row in source.rows(query):
        hand_history = row.get('HandHistory')
        if not hand_history:
            continue
        try:
            session = ET.fromstring(hand_history)
        except ET.ParseError:
            continue
        big_blind = extract_big_blind(session)
        if not big_blind or big_blind <= 0:
            continue
        for game in session.findall('game'):
            players = _parse_players(game)
            if not players:
                continue
            sb_player = _find_small_blind(game)
            position_map = _assign_positions_from_players(players, sb_player)
            if not position_map:
                continue
            stacks = {p['name']: p['chips'] for p in players}

            pot, contrib = _initial_pot_and_contrib(game, position_map)
            actions = _parse_preflop_actions(game, position_map)
            if not actions:
                continue

            active_players = set(position_map.keys())
            folded: set[str] = set()
            raise_count = 0
            calls_since_raise = 0
            calls_total = 0
            vpipped_players: Set[str] = set()
            hero_events: List[HeroEvent] = []

            for idx, action in enumerate(actions):
                name = action.name
                if name not in position_map:
                    continue
                position = position_map[name]
                stack = stacks.get(name, 0.0)

                if action.action == 'fold':
                    folded.add(name)
                    active_players.discard(name)
                    continue

                if action.action == 'check':
                    continue

                if action.action == 'call':
                    increment = max(action.amount - contrib.get(name, 0.0), 0.0)
                    if increment > 0:
                        pot += increment
                        contrib[name] = contrib.get(name, 0.0) + increment
                    calls_since_raise += 1
                    calls_total += 1
                    vpipped_players.add(name)
                    continue

                if action.action != 'raise':
                    continue

                increment = max(action.amount - contrib.get(name, 0.0), 0.0)
                pot_before = pot
                if increment <= 0:
                    continue
                if pot_before <= 0:
                    continue

                hero_stack_bb = stack / big_blind if big_blind else 0.0
                villain_stack_bb = 0.0
                for other_name, other_stack in stacks.items():
                    if other_name == name:
                        continue
                    villain_stack_bb = max(villain_stack_bb, other_stack / big_blind)
                effective_stack_bb = min(hero_stack_bb, villain_stack_bb)
                stack_bucket = _stack_bucket_for(effective_stack_bb)
                if not stack_bucket:
                    pot += increment
                    contrib[name] = contrib.get(name, 0.0) + increment
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                ratio = increment / pot_before if pot_before else 0.0
                bet_bucket = bucket_for_ratio(ratio)
                if not bet_bucket:
                    pot += increment
                    contrib[name] = contrib.get(name, 0.0) + increment
                    raise_count += 1
                    calls_since_raise = 0
                    continue

                situation_key = _situation_key(raise_count, calls_since_raise, calls_total)
                response = _classify_response_steps(actions, idx, name)
                players_behind = _count_players_to_act_steps(actions, idx, name)

                pot_before_bb = pot_before / big_blind
                invest_bb = increment / big_blind

                pot_bucket = _pot_bucket_for(pot_before_bb)
                vpip_ahead = len({player for player in vpipped_players if player != name})

                hero_events.append(
                    HeroEvent(
                        position=position,
                        stack_bucket=stack_bucket,
                        pot_bucket=pot_bucket,
                        situation_key=situation_key,
                        bet_bucket=bet_bucket,
                        response=response,
                        pot_before_bb=pot_before_bb,
                        invest_bb=invest_bb,
                        players_behind=players_behind,
                        vpip_ahead=vpip_ahead,
                        effective_stack_bb=effective_stack_bb,
                    )
                )

                pot += increment
                contrib[name] = contrib.get(name, 0.0) + increment
                raise_count += 1
                calls_since_raise = 0
                calls_total = 0
                vpipped_players.add(name)

            final_pot_bb = pot / big_blind
            remaining_players = {
                pname for pname, amount in contrib.items() if amount > 0 and pname not in folded
            }
            final_players = len(remaining_players)

            for event in hero_events:
                scenario = builder._scenario(
                    event.position,
                    event.stack_bucket,
                    event.pot_bucket,
                    event.vpip_ahead,
                    event.players_behind,
                )
                scenario.register(
                    event.bet_bucket,
                    event.response,
                    event.pot_before_bb,
                    event.invest_bb,
                    event.effective_stack_bb,
                    final_pot_bb,
                    final_players,
                    event.situation_key,
                )

            processed += 1
            if max_hands is not None and processed >= max_hands:
                break
        if max_hands is not None and processed >= max_hands:
            break

    return builder.build()


def write_response_curve_cache(output_path: Optional[Path] = None, *, max_hands: Optional[int] = None) -> Path:
    """Generate the response-curve cache JSON file.

    Returns the path written so callers can surface it to the user.
    """

    scenarios = build_response_curves(max_hands=max_hands)
    if not scenarios:
        scenarios = list(_SAMPLE_SCENARIOS)
    output_path = output_path or (build_data_paths().cache_dir / "preflop_response_curves.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for scenario in scenarios:
        payload.append(asdict(scenario))
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return output_path


__all__ = [
    "build_response_curves",
    "write_response_curve_cache",
]
