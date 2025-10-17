"""Build cacheable aggregates for the flop response matrix page."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from poker_analytics.config import build_data_paths
from poker_analytics.data.bet_sizing import bucket_for_ratio
from poker_analytics.data.cards import extract_big_blind
from poker_analytics.data.drivehud import DriveHudDataSource

BET_TYPES = {"5", "7"}
RAISE_TYPES = {"23", "7"}
CALL_TYPES = {"3"}
CHECK_TYPES = {"4"}
FOLD_TYPES = {"0"}
POST_TYPES = {"1", "2"}
ALL_IN_TYPES = {"7"}


@dataclass(frozen=True)
class PlayerInfo:
    name: str
    seat: int
    is_button: bool


def collect_flop_bet_events(
    source: Optional[DriveHudDataSource] = None,
    *,
    max_hands: Optional[int] = None,
) -> list[dict[str, object]]:
    """Return hero flop bet events enriched with classification metadata."""

    source = source or DriveHudDataSource.from_defaults()
    if not source.is_available():
        return []

    events: list[dict[str, object]] = []

    for row in source.rows("SELECT HandHistory FROM HandHistories"):
        hand_history = row.get("HandHistory")
        if not hand_history:
            continue
        try:
            events.extend(_events_from_hand_history(hand_history))
        except ET.ParseError:
            continue

        if max_hands is not None and len(events) >= max_hands:
            del events[max_hands:]
            break

    return events


def write_flop_response_cache(
    output_path: Optional[Path] = None,
    *,
    max_hands: Optional[int] = None,
    source: Optional[DriveHudDataSource] = None,
) -> Path:
    """Materialise the flop response matrix payload to disk."""

    from poker_analytics.services import flop_response_matrix as flop_matrix

    events = collect_flop_bet_events(source=source, max_hands=max_hands)
    payload = flop_matrix.build_flop_response_payload(events)

    data_paths = build_data_paths()
    data_paths.ensure_cache_dir()
    destination = output_path or (data_paths.cache_dir / "flop_response_matrix.json")
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    return destination


def _events_from_hand_history(hand_history: str) -> list[dict[str, object]]:
    root = ET.fromstring(hand_history)

    hero = _hero_name(root)
    if not hero:
        return []

    players = _parse_players(root)
    if not players or hero not in {player.name for player in players}:
        return []

    position_index = _position_index(players)
    position_labels = _position_labels(players)
    if hero not in position_index or hero not in position_labels:
        return []

    big_blind = extract_big_blind(root)
    if not big_blind or big_blind <= 0:
        return []

    hero_position_label = position_labels.get(hero)
    if not hero_position_label:
        return []

    player_contrib: Dict[str, float] = defaultdict(float)
    total_pot = 0.0
    active_players = {player.name for player in players}
    preflop_aggressor: Optional[str] = None
    events: list[dict[str, object]] = []

    rounds = sorted(root.findall(".//round"), key=lambda r: int(r.attrib.get("no", "0")))
    flop_player_count: Optional[int] = None
    flop_active_snapshot: Optional[set[str]] = None
    hero_event_recorded = False

    for round_elem in rounds:
        round_no = int(round_elem.attrib.get("no", "0"))
        actions = list(round_elem.findall("action"))

        if round_no == 1:
            for action_elem in actions:
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                if not player or not action_type:
                    continue

                amount = _safe_amount(action_elem)
                if amount > 0:
                    total_pot += amount

                if action_type in FOLD_TYPES:
                    active_players.discard(player)
                elif action_type not in CHECK_TYPES:
                    active_players.add(player)

                if action_type in RAISE_TYPES and amount > 0:
                    preflop_aggressor = player

        elif round_no == 2:
            if len(active_players) < 2:
                break
            if flop_player_count is None:
                flop_player_count = len(active_players)
                flop_active_snapshot = set(active_players)

            players_acted: set[str] = set()
            flop_bet_seen = False

            for idx, action_elem in enumerate(actions):
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                if not player or not action_type:
                    continue

                amount = _safe_amount(action_elem)
                pot_before = total_pot

                if (
                    not hero_event_recorded
                    and player == hero
                    and action_type in BET_TYPES
                    and amount > 0
                    and not flop_bet_seen
                    and flop_player_count
                    and flop_player_count >= 2
                    and flop_active_snapshot
                ):
                    bet_type = _classify_bet(
                        hero,
                        preflop_aggressor,
                        players_acted,
                        flop_active_snapshot,
                    )
                    hero_in_position = _hero_in_position(hero, position_index, flop_active_snapshot)

                    ratio = (amount / pot_before) if pot_before > 0 else None
                    bucket = bucket_for_ratio(ratio)
                    if bucket is not None and ratio is not None:
                        tolerance = max(1e-6, big_blind * 1e-4)
                        is_one_bb = math.isfinite(big_blind) and abs(amount - big_blind) <= tolerance
                        outcome = _villain_outcome(actions[idx + 1 :], hero)
                        events.append(
                            {
                                "hero_position": hero_position_label,
                                "bet_type": bet_type,
                                "in_position": hero_in_position,
                                "player_count": flop_player_count,
                                "ratio": ratio,
                                "bucket_key": bucket.key,
                                "is_all_in": action_type in ALL_IN_TYPES,
                                "is_one_bb": is_one_bb,
                                "villain_outcome": outcome,
                            }
                        )
                        hero_event_recorded = True

                if action_type in BET_TYPES | RAISE_TYPES and amount > 0:
                    flop_bet_seen = True

                if action_type in FOLD_TYPES:
                    active_players.discard(player)

                if amount > 0:
                    total_pot += amount

                players_acted.add(player)

        else:
            for action_elem in actions:
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                amount = _safe_amount(action_elem)
                if amount > 0:
                    total_pot += amount
                if player and action_type in FOLD_TYPES:
                    active_players.discard(player)

    return events


def _hero_name(root: ET.Element) -> Optional[str]:
    nickname = root.findtext(".//game/general/nickname") or root.findtext(".//general/nickname")
    if nickname:
        return nickname.strip()
    return None


def _parse_players(root: ET.Element) -> list[PlayerInfo]:
    players_node = root.find(".//game/general/players")
    players: list[PlayerInfo] = []
    if players_node is None:
        return players
    for player_elem in players_node.findall("player"):
        name = player_elem.attrib.get("name")
        seat_text = player_elem.attrib.get("seat")
        if not name or not seat_text:
            continue
        try:
            seat = int(seat_text)
        except ValueError:
            continue
        is_button = player_elem.attrib.get("dealer") == "1"
        players.append(PlayerInfo(name=name, seat=seat, is_button=is_button))
    return players


def _position_index(players: Sequence[PlayerInfo]) -> Dict[str, int]:
    if not players:
        return {}
    sorted_players = sorted(players, key=lambda p: p.seat)
    button_index = next((i for i, p in enumerate(sorted_players) if p.is_button), None)
    if button_index is None:
        button_index = 0
    order_from_button = sorted_players[button_index:] + sorted_players[:button_index]
    action_order = order_from_button[1:] + order_from_button[:1]
    return {player.name: idx for idx, player in enumerate(action_order)}


def _position_labels(players: Sequence[PlayerInfo]) -> Dict[str, str]:
    if not players:
        return {}
    sorted_players = sorted(players, key=lambda p: p.seat)
    button_index = next((i for i, p in enumerate(sorted_players) if p.is_button), None)
    if button_index is None:
        button_index = 0
    order_from_button = sorted_players[button_index:] + sorted_players[:button_index]
    canonical = [
        "BTN",
        "SB",
        "BB",
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
    ]
    labels: Dict[str, str] = {}
    for idx, player in enumerate(order_from_button):
        label = canonical[idx] if idx < len(canonical) else f"P{idx}"
        labels[player.name] = label
    return labels


def _safe_amount(action_elem: ET.Element) -> float:
    try:
        return float(action_elem.attrib.get("sum") or 0.0)
    except ValueError:
        return 0.0


def _classify_bet(
    hero: str,
    preflop_aggressor: Optional[str],
    players_acted: Iterable[str],
    flop_active_players: Iterable[str],
) -> str:
    acted_set = set(players_acted)
    active_set = set(flop_active_players)

    if preflop_aggressor == hero:
        return "cbet"
    if preflop_aggressor and preflop_aggressor in active_set and preflop_aggressor not in acted_set:
        return "donk"
    return "stab"


def _hero_in_position(hero: str, position_index: Dict[str, int], active_players: Iterable[str]) -> bool:
    indices = [position_index[player] for player in active_players if player in position_index]
    if not indices:
        return False
    hero_index = position_index.get(hero)
    if hero_index is None:
        return False
    return hero_index == max(indices)


def _villain_outcome(actions: Sequence[ET.Element], hero: str) -> str:
    outcome = "fold"
    for action_elem in actions:
        player = action_elem.attrib.get("player")
        if not player or player == hero:
            break
        act_type = action_elem.attrib.get("type")
        if act_type in FOLD_TYPES or act_type in CHECK_TYPES:
            continue
        if act_type in CALL_TYPES:
            outcome = "call"
        if act_type in BET_TYPES or act_type in RAISE_TYPES:
            return "raise"
    return outcome


__all__ = ["collect_flop_bet_events", "write_flop_response_cache"]
