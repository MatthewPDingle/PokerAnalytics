"""Aggregations for hero performance by opponent count using DriveHUD exports."""

from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from poker_analytics.data.drivehud import DriveHudDataSource

CALL_TYPES = {"3"}
RAISE_TYPES = {"7", "23"}
VOLUNTARY_TYPES = CALL_TYPES | RAISE_TYPES

# Position labels by player count, following canonical poker ordering.
# Table positions collapse from the middle for shorter tables.
# Heads-up (2 players): SB is also the button.
POSITIONS_BY_COUNT = {
    2: ["SB", "BB"],
    3: ["SB", "BB", "BTN"],
    4: ["SB", "BB", "CO", "BTN"],
    5: ["SB", "BB", "HJ", "CO", "BTN"],
    6: ["SB", "BB", "LJ", "HJ", "CO", "BTN"],
    7: ["SB", "BB", "UTG", "LJ", "HJ", "CO", "BTN"],
    8: ["SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO", "BTN"],
    9: ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN"],
}

# Canonical position order for sorting and display
POSITION_ORDER = ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "UNKNOWN"]
POSITION_SORT_KEY = {name: idx for idx, name in enumerate(POSITION_ORDER)}


@dataclass
class Accumulator:
    hand_count: int = 0
    net_cents: int = 0
    net_bb: float = 0.0
    vpip_hands: int = 0
    pfr_hands: int = 0
    three_bet_hands: int = 0
    three_bet_opportunities: int = 0
    pot_bb_sum: float = 0.0
    pot_samples: int = 0

    def record(
        self,
        net_cents: int,
        net_bb: float,
        vpip: bool,
        pfr: bool,
        three_bet: bool,
        three_bet_opportunity: bool,
        pot_bb: float,
    ) -> None:
        self.hand_count += 1
        self.net_cents += net_cents
        self.net_bb += net_bb
        if vpip:
            self.vpip_hands += 1
        if pfr:
            self.pfr_hands += 1
        if three_bet:
            self.three_bet_hands += 1
        if three_bet_opportunity:
            self.three_bet_opportunities += 1
        if pot_bb > 0:
            self.pot_bb_sum += pot_bb
            self.pot_samples += 1

    def as_payload(self) -> dict[str, float | int]:
        hands = self.hand_count
        net_bb = self.net_bb
        net_dollars = self.net_cents / 100.0
        vpip_pct = (self.vpip_hands / hands * 100.0) if hands else 0.0
        pfr_pct = (self.pfr_hands / hands * 100.0) if hands else 0.0
        three_bet_pct = (
            self.three_bet_hands / self.three_bet_opportunities * 100.0
            if self.three_bet_opportunities
            else 0.0
        )
        bb_per_100 = (net_bb / hands * 100.0) if hands else 0.0
        avg_pot_bb = (self.pot_bb_sum / self.pot_samples) if self.pot_samples else 0.0
        return {
            "hand_count": hands,
            "net_bb": round(net_bb, 2),
            "net_dollars": round(net_dollars, 2),
            "bb_per_100": round(bb_per_100, 2),
            "vpip_pct": round(vpip_pct, 2),
            "pfr_pct": round(pfr_pct, 2),
            "three_bet_pct": round(three_bet_pct, 2),
            "avg_pot_bb": round(avg_pot_bb, 2),
            "raw": {
                "hand_count": hands,
                "net_cents": self.net_cents,
                "net_bb": self.net_bb,
                "vpip_hands": self.vpip_hands,
                "pfr_hands": self.pfr_hands,
                "three_bet_hands": self.three_bet_hands,
                "three_bet_opportunities": self.three_bet_opportunities,
                "pot_bb_sum": self.pot_bb_sum,
                "pot_samples": self.pot_samples,
            },
        }


def _parse_float(value: Optional[str]) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _extract_big_blind(game: ET.Element, session_gametype: Optional[str]) -> Optional[float]:
    round_zero = game.find("round[@no='0']")
    if round_zero is not None:
        for action in round_zero.findall('action'):
            if action.get('type') == '2':
                bb = _parse_float(action.get('sum'))
                if bb > 0:
                    return bb
    if session_gametype:
        match = re.search(r"/\$(\d+(?:\.\d+)?)", session_gametype)
        if match:
            try:
                bb = float(match.group(1))
                if bb > 0:
                    return bb
            except ValueError:
                pass
    return None


def _assign_positions_from_actions(
    dealt_players: set[str],
    small_blind_name: Optional[str],
    big_blind_name: Optional[str],
    acting_order: List[str],
    dealer_name: Optional[str] = None,
) -> Dict[str, str]:
    count = len(dealt_players)
    order = POSITIONS_BY_COUNT.get(count)
    if not order:
        return {}

    mapping: Dict[str, str] = {}

    # Assign blinds
    if count >= 1 and small_blind_name and small_blind_name in dealt_players:
        mapping[small_blind_name] = order[0]
    if count >= 2 and big_blind_name and big_blind_name in dealt_players:
        mapping[big_blind_name] = order[1]

    # Handle case where SB wasn't posted but BB was (dead button, missing blind scenarios)
    # Simply don't assign SB - use action order for remaining positions
    # (This allows us to investigate what DriveHUD actually does in these cases)

    remaining_positions = order[2:]
    remaining_players = [name for name in acting_order if name in dealt_players and name not in mapping]

    for player, position_label in zip(remaining_players, remaining_positions):
        mapping[player] = position_label

    return mapping


def _assign_positions_from_seats(players: List[dict], dealt_players: set[str], small_blind_name: Optional[str], dealer_name: Optional[str] = None) -> Dict[str, str]:
    if not players or not dealt_players:
        return {}

    count = len(dealt_players)
    order = POSITIONS_BY_COUNT.get(count)
    if not order or len(order) != count:
        return {}

    # Get only dealt players, sorted by seat
    seat_sorted = sorted([p for p in players if p['name'] in dealt_players], key=lambda p: p['seat'])

    # If we have a dealer, use them as BTN and rotate backwards
    if dealer_name and dealer_name in dealt_players and 'BTN' in order:
        # Find dealer in the seat-sorted list
        dealer_idx = next((i for i, p in enumerate(seat_sorted) if p['name'] == dealer_name), None)
        if dealer_idx is not None:
            # Build rotation starting from dealer as BTN and going backwards in seats
            rotation: List[dict] = []
            for i in range(count):
                # Go backwards from dealer
                idx = (dealer_idx - (count - 1 - i)) % len(seat_sorted)
                rotation.append(seat_sorted[idx])

            # Assign all positions normally based on seat rotation from dealer
            mapping: Dict[str, str] = {}
            for position_label, player in zip(order, rotation):
                mapping[player['name']] = position_label
            return mapping

    # Fallback: use SB-based rotation (same as before)
    name_to_player = {p['name']: p for p in seat_sorted}
    if small_blind_name and small_blind_name in name_to_player:
        sb_seat = name_to_player[small_blind_name]['seat']
    else:
        sb_seat = seat_sorted[0]['seat']

    start_index = next((i for i, p in enumerate(seat_sorted) if p['seat'] == sb_seat), 0)

    rotation_list: List[dict] = []
    for i in range(count):
        idx = (start_index + i) % len(seat_sorted)
        rotation_list.append(seat_sorted[idx])

    mapping: Dict[str, str] = {}
    for position_label, player in zip(order, rotation_list):
        mapping[player['name']] = position_label

    return mapping


def _evaluate_preflop(actions: Iterable[dict], hero_name: str) -> tuple[bool, bool, bool, bool]:
    vpip = False
    pfr = False
    three_bet = False
    three_bet_opportunity = False
    raise_count = 0

    for action in actions:
        actor = action.get('player')
        action_type = action.get('type') or ""

        if actor == hero_name:
            if raise_count >= 1:
                three_bet_opportunity = True
            if action_type in VOLUNTARY_TYPES:
                vpip = True
            if action_type in RAISE_TYPES:
                pfr = True
                if raise_count >= 1:
                    three_bet = True
        if action_type in RAISE_TYPES:
            raise_count += 1

    return vpip, pfr, three_bet, three_bet_opportunity


def _parse_game(
    game: ET.Element,
    hero_name: str,
    session_gametype: Optional[str],
) -> Optional[tuple[int, str, int, float, float, bool, bool, bool, bool]]:
    players_section = game.find('./general/players')
    if players_section is None:
        return None

    players: List[dict] = []
    dealer_name: Optional[str] = None
    for player in players_section.findall('player'):
        name = player.get('name')
        if not name:
            continue
        is_dealer = player.get('dealer') == '1'
        if is_dealer:
            dealer_name = name
        players.append(
            {
                'name': name,
                'seat': int(player.get('seat') or 0),
                'dealer': is_dealer,
                'bet': _parse_float(player.get('bet')),
                'win': _parse_float(player.get('win')),
            }
        )

    if not players:
        return None

    hero = next((p for p in players if p['name'] == hero_name), None)
    if not hero:
        return None

    total_players = len(players)
    opponents = total_players - 1
    if opponents < 1:
        return None

    big_blind = _extract_big_blind(game, session_gametype)
    if not big_blind:
        return None

    net = hero['win'] - hero['bet']
    net_cents = int(round(net * 100))
    net_bb = net / big_blind if big_blind else 0.0
    pot_bb = sum(p['bet'] for p in players) / big_blind if big_blind else 0.0

    preflop_round = game.find("round[@no='1']")
    if preflop_round is None:
        return None
    dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}
    if hero_name not in dealt_players:
        return None

    preflop_actions = [
        {'player': action.get('player'), 'type': action.get('type')}
        for action in preflop_round.findall('action')
    ]
    vpip, pfr, three_bet, opportunity = _evaluate_preflop(preflop_actions, hero_name)

    acting_order: List[str] = []
    for action in preflop_actions:
        name = action.get('player')
        if name and name not in acting_order:
            acting_order.append(name)

    round_zero = game.find("round[@no='0']")
    small_blind_name = None
    big_blind_name = None
    if round_zero is not None:
        for action in round_zero.findall('action'):
            if action.get('type') == '1' and action.get('player'):
                small_blind_name = action.get('player')
            if action.get('type') == '2' and action.get('player'):
                big_blind_name = action.get('player')

    # Try seat-based positioning first (DriveHUD uses dealer-aware seat rotation)
    position_map = _assign_positions_from_seats(players, dealt_players, small_blind_name, dealer_name)
    # Fall back to action-based if seat-based didn't assign hero
    if hero_name not in position_map:
        position_map = _assign_positions_from_actions(dealt_players, small_blind_name, big_blind_name, acting_order, dealer_name)
    position = position_map.get(hero_name, 'UNKNOWN')

    return opponents, position, net_cents, net_bb, pot_bb, vpip, pfr, three_bet, opportunity


def get_opponent_count_performance() -> List[dict[str, object]]:
    """Return hero performance aggregated by opponent count and position."""

    source = DriveHudDataSource.from_defaults()
    if not source.is_available():
        return []

    overall: Dict[int, Accumulator] = defaultdict(Accumulator)
    by_position: Dict[int, Dict[str, Accumulator]] = defaultdict(lambda: defaultdict(Accumulator))
    timeline_records: List[tuple[str, float, Optional[int], int]] = []

    sequence = 0

    try:
        history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId')
    except sqlite3.OperationalError:
        return []

    for row in history_rows:
        text = row.get('HandHistory')
        if not text:
            continue
        try:
            session = ET.fromstring(text)
        except ET.ParseError:
            continue

        session_general = session.find('general')
        hero_name = session_general.findtext('nickname') if session_general is not None else None
        gametype = session_general.findtext('gametype') if session_general is not None else None
        if not hero_name:
            continue

        hand_number_value: Optional[int] = None
        raw_hand_number = row.get('HandNumber')
        if raw_hand_number is not None:
            try:
                hand_number_value = int(str(raw_hand_number))
            except ValueError:
                hand_number_value = None
        if hand_number_value is None:
            try:
                hand_number_value = int(row.get('HandHistoryId'))
            except (TypeError, ValueError):
                hand_number_value = None

        for game in session.findall('game'):
            parsed = _parse_game(game, hero_name, gametype)
            if not parsed:
                continue
            (
                opponents,
                position,
                net_cents,
                net_bb,
                pot_bb,
                vpip,
                pfr,
                three_bet,
                opportunity,
            ) = parsed

            overall_acc = overall[opponents]
            overall_acc.record(net_cents, net_bb, vpip, pfr, three_bet, opportunity, pot_bb)

            position_acc = by_position[opponents][position]
            position_acc.record(net_cents, net_bb, vpip, pfr, three_bet, opportunity, pot_bb)

            sequence += 1
            timeline_records.append((position, net_bb, hand_number_value, sequence))

    results: List[dict[str, object]] = []
    for opponents in sorted(overall):
        overall_metrics = overall[opponents].as_payload()
        positions_payload: List[dict[str, object]] = []
        for position, acc in sorted(
            by_position[opponents].items(),
            key=lambda item: (POSITION_SORT_KEY.get(item[0], 999), item[0]),
        ):
            metrics = acc.as_payload()
            if metrics["hand_count"]:
                positions_payload.append({
                    "position": position,
                    "metrics": metrics,
                })

        results.append(
            {
                "opponent_count": opponents,
                "overall": overall_metrics,
                "positions": positions_payload,
            }
        )

    timeline_records.sort(key=lambda item: (
        item[2] is None,
        item[2] if item[2] is not None else float('inf'),
        item[3],
    ))
    timeline_payload = []
    for idx, (position, net_bb, _, _) in enumerate(timeline_records, 1):
        timeline_payload.append(
            {
                "hand_index": idx,
                "position": position,
                "net_bb": net_bb,
            }
        )

    return {
        "buckets": results,
        "timeline": timeline_payload,
    }


__all__ = ["get_opponent_count_performance"]
