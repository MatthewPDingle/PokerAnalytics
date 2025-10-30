"""Build cacheable aggregates for the flop response matrix page."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from poker_analytics.config import build_data_paths
from poker_analytics.data.bet_sizing import bucket_for_ratio
from poker_analytics.data.cards import extract_big_blind
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.data.flop_hand_categories import classify_flop_hand, parse_board_cards, parse_hole_cards
from poker_analytics.data.textures import texture_keys

BET_TYPES = {"5", "7"}
RAISE_TYPES = {"23", "7"}
CALL_TYPES = {"3"}
CHECK_TYPES = {"4"}
FOLD_TYPES = {"0"}
POST_TYPES = {"1", "2"}
ALL_IN_TYPES = {"7"}

LINE_PREFIX_MAP = {
    ("call", True): "xc",
    ("call", False): "c",
    ("raise", True): "xr",
    ("raise", False): "r",
}

LINE_SUFFIX_MAP = {
    "bet": "b",
    "raise": "b",
    "check": "x",
    "call": "c",
    "fold": "f",
}


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
    stake_policy = StakePolicy.from_environment()

    for row in source.rows("SELECT HandHistory FROM HandHistories"):
        hand_history = row.get("HandHistory")
        if not hand_history:
            continue
        try:
            events.extend(_events_from_hand_history(hand_history, stake_policy))
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
    stake_policy = StakePolicy.from_environment()
    destination = output_path or (data_paths.cache_dir / f"flop_response_matrix_{stake_policy.cache_token()}.json")
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    return destination


def _events_from_hand_history(hand_history: str, stake_policy: StakePolicy) -> list[dict[str, object]]:
    root = ET.fromstring(hand_history)

    events: list[dict[str, object]] = []

    events: list[dict[str, object]] = []

    events: list[dict[str, object]] = []

    events: list[dict[str, object]] = []

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
    if not stake_policy.matches(big_blind):
        return []

    player_hole_cards = _extract_all_hole_cards(root)
    hero_hole_cards = player_hole_cards.get(hero, [])
    hero_hole_cards_text = " ".join(card for _, _, card in hero_hole_cards) if hero_hole_cards else None
    flop_cards = _extract_flop_cards(root)
    flop_cards_text = " ".join(card for _, _, card in flop_cards) if flop_cards else None

    player_contrib: Dict[str, float] = defaultdict(float)
    total_pot = 0.0
    active_players = {player.name for player in players}
    preflop_aggressor: Optional[str] = None
    events: list[dict[str, object]] = []

    rounds = sorted(root.findall(".//round"), key=lambda r: int(r.attrib.get("no", "0")))
    flop_player_count: Optional[int] = None
    flop_active_snapshot: Optional[set[str]] = None
    flop_event_recorded = False

    current_event: Optional[dict[str, object]] = None
    current_event_index: Optional[int] = None
    current_event_round: Optional[int] = None

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
                    not flop_event_recorded
                    and action_type in BET_TYPES
                    and amount > 0
                    and not flop_bet_seen
                    and flop_player_count
                    and flop_player_count >= 2
                    and flop_active_snapshot
                ):
                    bet_type = _classify_bet(
                        player,
                        preflop_aggressor,
                        players_acted,
                        flop_active_snapshot,
                    )
                    bettor_position = position_labels.get(player, "UNKNOWN")
                    bettor_in_position = _bettor_in_position(player, position_index, flop_active_snapshot)

                    is_hero_event = player == hero
                    if is_hero_event:
                        flop_event_recorded = True
                        current_event = None
                        current_event_index = None
                        current_event_round = None
                    else:
                        bettor_cards = player_hole_cards.get(player, [])
                        hand_primary = None
                        has_flush_draw = False
                        has_oesd_dg = False
                        if bettor_cards and flop_cards and len(bettor_cards) == 2 and len(flop_cards) == 3:
                            classification = classify_flop_hand(bettor_cards, flop_cards)
                            hand_primary = classification.primary
                            has_flush_draw = classification.has_flush_draw
                            has_oesd_dg = classification.has_oesd_dg

                        ratio = (amount / pot_before) if pot_before > 0 else None
                        bucket = bucket_for_ratio(ratio)
                        if bucket is not None and ratio is not None:
                            tolerance = max(1e-6, big_blind * 1e-4)
                            is_one_bb = math.isfinite(big_blind) and abs(amount - big_blind) <= tolerance
                            outcome = _villain_outcome(actions[idx + 1 :], player)
                            total_added = amount
                            total_added_bb = amount / big_blind if big_blind else 0.0
                            responses = _collect_flop_responses(
                                actions[idx + 1 :],
                                player,
                                player_hole_cards,
                                flop_cards,
                            )
                            event_record = {
                                "hero_position": bettor_position,
                                "bettor": player,
                                "bet_type": bet_type,
                                "in_position": bettor_in_position,
                                "player_count": flop_player_count,
                                "ratio": ratio,
                                "bucket_key": bucket.key,
                                "is_all_in": action_type in ALL_IN_TYPES,
                                "is_one_bb": is_one_bb,
                                "villain_outcome": outcome,
                                "bettor_is_hero": False,
                                "hand_primary": hand_primary,
                                "has_flush_draw": has_flush_draw,
                                "has_oesd_dg": has_oesd_dg,
                                "hole_cards": (
                                    " ".join(card for _, _, card in bettor_cards) if bettor_cards else None
                                ),
                                "hero_hole_cards": hero_hole_cards_text if is_hero_event else None,
                                "flop_cards": flop_cards_text,
                                "pot_before_bb": (pot_before / big_blind) if big_blind else None,
                                "total_added_flop": total_added,
                                "total_added_flop_bb": total_added_bb,
                                "total_added_all": total_added,
                                "total_added_all_bb": total_added_bb,
                                "responses": responses,
                            }
                            events.append(event_record)
                            current_event = event_record
                            current_event_index = idx
                            current_event_round = round_no
                            flop_event_recorded = True

            if action_type in BET_TYPES | RAISE_TYPES and amount > 0:
                flop_bet_seen = True

                if action_type in FOLD_TYPES:
                    active_players.discard(player)

            if amount > 0:
                total_pot += amount
                if (
                    current_event is not None
                    and current_event_index is not None
                    and idx > current_event_index
                    and current_event_round == round_no
                ):
                    increment = amount
                    increment_bb = amount / big_blind if big_blind else 0.0
                    current_event["total_added_flop"] = float(current_event.get("total_added_flop", 0.0)) + increment
                    current_event["total_added_flop_bb"] = float(current_event.get("total_added_flop_bb", 0.0)) + increment_bb
                    current_event["total_added_all"] = float(current_event.get("total_added_all", 0.0)) + increment
                    current_event["total_added_all_bb"] = float(current_event.get("total_added_all_bb", 0.0)) + increment_bb

                players_acted.add(player)

        else:
            for action_elem in actions:
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                amount = _safe_amount(action_elem)
                if amount > 0:
                    total_pot += amount
                    if current_event is not None:
                        increment = amount
                        increment_bb = amount / big_blind if big_blind else 0.0
                        current_event["total_added_all"] = float(current_event.get("total_added_all", 0.0)) + increment
                        current_event["total_added_all_bb"] = float(current_event.get("total_added_all_bb", 0.0)) + increment_bb
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
    bettor: str,
    preflop_aggressor: Optional[str],
    players_acted: Iterable[str],
    flop_active_players: Iterable[str],
) -> str:
    acted_set = set(players_acted)
    active_set = set(flop_active_players)

    if preflop_aggressor == bettor:
        return "cbet"
    if preflop_aggressor and preflop_aggressor in active_set and preflop_aggressor not in acted_set:
        return "donk"
    return "stab"


def _bettor_in_position(bettor: str, position_index: Dict[str, int], active_players: Iterable[str]) -> bool:
    indices = [position_index[player] for player in active_players if player in position_index]
    if not indices:
        return False
    bettor_index = position_index.get(bettor)
    if bettor_index is None:
        return False
    return bettor_index == max(indices)


def _villain_outcome(actions: Sequence[ET.Element], bettor: str) -> str:
    outcome = "fold"
    for action_elem in actions:
        player = action_elem.attrib.get("player")
        if not player or player == bettor:
            break
        act_type = action_elem.attrib.get("type")
        if act_type in FOLD_TYPES or act_type in CHECK_TYPES:
            continue
        if act_type in CALL_TYPES:
            outcome = "call"
        if act_type in BET_TYPES or act_type in RAISE_TYPES:
            return "raise"
    return outcome


def _extract_all_hole_cards(root: ET.Element) -> Dict[str, List[tuple[str, int, str]]]:
    mapping: Dict[str, List[tuple[str, int, str]]] = {}
    for node in root.findall('.//round[@no="1"]/cards'):
        player = node.attrib.get("player")
        if not player:
            continue
        source = node.attrib.get("cards") or node.text
        cards = parse_hole_cards(source)
        if len(cards) == 2:
            mapping[player] = cards
    return mapping


def _extract_flop_cards(root: ET.Element) -> List[tuple[str, int, str]]:
    for node in root.findall('.//round[@no="2"]/cards'):
        node_type = (node.attrib.get("type") or "").lower()
        if node_type == "flop":
            source = node.attrib.get("cards") or node.text
            cards = parse_board_cards(source)
            if len(cards) == 3:
                return cards
    return []


def _line_events_from_hand_history(
    hand_history: str,
    stake_policy: StakePolicy,
    *,
    line_key: Optional[str] = None,
) -> list[dict[str, object]]:
    root = ET.fromstring(hand_history)

    events: list[dict[str, object]] = []

    hero = _hero_name(root)
    if not hero:
        return events

    players = _parse_players(root)
    if not players or hero not in {player.name for player in players}:
        return events

    position_index = _position_index(players)
    position_labels = _position_labels(players)
    if hero not in position_index or hero not in position_labels:
        return events

    big_blind = extract_big_blind(root)
    if not big_blind or big_blind <= 0:
        return events
    if not stake_policy.matches(big_blind):
        return events

    player_hole_cards = _extract_all_hole_cards(root)
    flop_cards = _extract_flop_cards(root)
    flop_cards_text = " ".join(card for _, _, card in flop_cards) if flop_cards else None
    if not flop_cards:
        return events

    active_players = {player.name for player in players}
    player_states: Dict[str, dict[str, object]] = {name: {"checked": False} for name in active_players}

    total_pot = 0.0
    preflop_aggressor: Optional[str] = None
    flop_player_count: Optional[int] = None
    flop_active_snapshot: Optional[set[str]] = None
    flop_first_bet: Optional[dict[str, object]] = None
    flop_responses: Dict[str, dict[str, object]] = {}

    rounds = sorted(root.findall(".//round"), key=lambda r: int(r.attrib.get("no", "0")))

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

            players_acted: set[str] = set()
            for idx, action_elem in enumerate(actions):
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                if not player or not action_type:
                    continue

                state = player_states.setdefault(player, {"checked": False})
                amount = _safe_amount(action_elem)
                pot_before = total_pot

                if action_type in CHECK_TYPES:
                    state["checked"] = True

                if action_type in BET_TYPES | RAISE_TYPES:
                    if flop_first_bet is None:
                        flop_active_snapshot = set(active_players)
                        bet_type = _classify_bet(player, preflop_aggressor, players_acted, flop_active_snapshot)
                        flop_first_bet = {"bet_type": bet_type}
                    total_pot += amount
                    players_acted.add(player)
                    continue

                if action_type in CALL_TYPES and flop_first_bet is not None:
                    if player == hero:
                        players_acted.add(player)
                        if amount > 0:
                            total_pot += amount
                        continue
                    responder_cards = player_hole_cards.get(player, [])
                    classification = None
                    if responder_cards and len(responder_cards) == 2 and len(flop_cards) == 3:
                        classification = classify_flop_hand(responder_cards, flop_cards)
                    prefix = LINE_PREFIX_MAP.get(("call", state.get("checked", False)))
                    if prefix is None:
                        players_acted.add(player)
                        if amount > 0:
                            total_pot += amount
                        continue
                    flop_responses[player] = {
                        "prefix": prefix,
                        "response_type": "call",
                        "bet_type": flop_first_bet.get("bet_type"),
                        "hero_position": position_labels.get(player, "UNKNOWN"),
                        "in_position": _bettor_in_position(player, position_index, flop_active_snapshot or active_players),
                        "player_count": flop_player_count,
                        "hand_primary": classification.primary if classification else None,
                        "has_flush_draw": classification.has_flush_draw if classification else False,
                        "has_oesd_dg": classification.has_oesd_dg if classification else False,
                        "hole_cards": " ".join(card for _, _, card in responder_cards) if responder_cards else None,
                        "responder_is_hero": player == hero,
                        "flop_texture_keys": texture_keys(flop_cards_text),
                    }
                elif action_type in RAISE_TYPES and flop_first_bet is not None:
                    if player == hero:
                        players_acted.add(player)
                        if amount > 0:
                            total_pot += amount
                        continue
                    responder_cards = player_hole_cards.get(player, [])
                    classification = None
                    if responder_cards and len(responder_cards) == 2 and len(flop_cards) == 3:
                        classification = classify_flop_hand(responder_cards, flop_cards)
                    prefix = LINE_PREFIX_MAP.get(("raise", state.get("checked", False)))
                    if prefix is None:
                        players_acted.add(player)
                        if amount > 0:
                            total_pot += amount
                        continue
                    flop_responses[player] = {
                        "prefix": prefix,
                        "response_type": "raise",
                        "bet_type": flop_first_bet.get("bet_type"),
                        "hero_position": position_labels.get(player, "UNKNOWN"),
                        "in_position": _bettor_in_position(player, position_index, flop_active_snapshot or active_players),
                        "player_count": flop_player_count,
                        "hand_primary": classification.primary if classification else None,
                        "has_flush_draw": classification.has_flush_draw if classification else False,
                        "has_oesd_dg": classification.has_oesd_dg if classification else False,
                        "hole_cards": " ".join(card for _, _, card in responder_cards) if responder_cards else None,
                        "responder_is_hero": player == hero,
                        "flop_texture_keys": texture_keys(flop_cards_text),
                    }

                if amount > 0:
                    total_pot += amount

                if action_type in FOLD_TYPES:
                    active_players.discard(player)

                players_acted.add(player)

        elif round_no == 3 and flop_responses:
            turn_actions: Dict[str, dict[str, object]] = {}
            for idx, action_elem in enumerate(actions):
                player = action_elem.attrib.get("player")
                action_type = action_elem.attrib.get("type")
                if not player or not action_type:
                    continue

                amount = _safe_amount(action_elem)
                pot_before = total_pot

                if player not in turn_actions:
                    if action_type in BET_TYPES:
                        code = "bet"
                    elif action_type in RAISE_TYPES:
                        code = "raise"
                    elif action_type in CHECK_TYPES:
                        code = "check"
                    elif action_type in CALL_TYPES:
                        code = "call"
                    elif action_type in FOLD_TYPES:
                        code = "fold"
                    else:
                        code = None
                    if code is not None:
                        turn_actions[player] = {
                            "code": code,
                            "amount": amount,
                            "pot_before": pot_before,
                            "sub_actions": actions[idx + 1 :],
                        }

                if amount > 0:
                    total_pot += amount
                if action_type in FOLD_TYPES:
                    active_players.discard(player)

            for player, info in flop_responses.items():
                action_info = turn_actions.get(player)
                if not action_info:
                    continue
                suffix = LINE_SUFFIX_MAP.get(action_info["code"])
                if suffix != "b":
                    continue
                computed_line_key = f"{info['prefix']}_turn_{suffix}"
                if line_key and computed_line_key != line_key:
                    continue
                pot_before_turn = action_info["pot_before"]
                amount = action_info["amount"]
                ratio = (amount / pot_before_turn) if pot_before_turn > 0 else 0.0
                bucket = bucket_for_ratio(ratio)
                if bucket is None:
                    continue
                outcome = _resolve_bet_outcome(action_info["sub_actions"], player)
                event_record = {
                    "line_key": computed_line_key,
                    "response_type": info["response_type"],
                    "hero_position": info.get("hero_position", "UNKNOWN"),
                    "bet_type": info.get("bet_type"),
                    "position": "IP" if info.get("in_position") else "OOP",
                    "player_count": info.get("player_count") or len(active_players),
                    "turn_bucket_key": bucket.key,
                    "turn_ratio": ratio,
                    "outcome": outcome,
                    "hand_primary": info.get("hand_primary"),
                    "has_flush_draw": info.get("has_flush_draw"),
                    "has_oesd_dg": info.get("has_oesd_dg"),
                    "hole_cards": info.get("hole_cards"),
                    "pot_before_turn_bb": pot_before_turn / big_blind,
                    "bet_amount_bb": amount / big_blind,
                    "flop_texture_keys": info.get("flop_texture_keys") or texture_keys(flop_cards_text),
                    "bettor_is_hero": False,
                    "responder_is_hero": bool(info.get("responder_is_hero")),
                }
                events.append(event_record)

        else:
            for action_elem in actions:
                amount = _safe_amount(action_elem)
                if amount > 0:
                    total_pot += amount

    return events


def collect_line_events(
    source: Optional[DriveHudDataSource] = None,
    *,
    line_key: Optional[str] = None,
    max_hands: Optional[int] = None,
) -> list[dict[str, object]]:
    source = source or DriveHudDataSource.from_defaults()
    if not source.is_available():
        return []

    events: list[dict[str, object]] = []
    stake_policy = StakePolicy.from_environment()

    for row in source.rows("SELECT HandHistory FROM HandHistories"):
        hand_history = row.get("HandHistory")
        if not hand_history:
            continue
        try:
            events.extend(_line_events_from_hand_history(hand_history, stake_policy, line_key=line_key))
        except ET.ParseError:
            continue

        if max_hands is not None and len(events) >= max_hands:
            del events[max_hands:]
            break

    return events


def _resolve_bet_outcome(actions: Sequence[ET.Element], bettor: str) -> str:
    outcome = "fold"
    has_call = False
    for action_elem in actions:
        player = action_elem.attrib.get("player")
        if not player or player == bettor:
            break
        act_type = action_elem.attrib.get("type")
        if act_type in FOLD_TYPES or act_type in CHECK_TYPES:
            continue
        if act_type in CALL_TYPES:
            has_call = True
        if act_type in BET_TYPES or act_type in RAISE_TYPES:
            return "raise"
    if has_call:
        return "call"
    return outcome


__all__ = [
    "collect_flop_bet_events",
    "collect_line_events",
    "write_flop_response_cache",
]
def _collect_flop_responses(
    subsequent_actions: Sequence[ET.Element],
    bettor: str,
    player_hole_cards: Mapping[str, List[tuple[str, int, str]]],
    flop_cards: Sequence[tuple[str, int, str]],
) -> list[dict[str, object]]:
    responses: list[dict[str, object]] = []
    seen_players: set[str] = set()

    for action_elem in subsequent_actions:
        player = action_elem.attrib.get("player")
        action_type = action_elem.attrib.get("type")
        if not player or not action_type:
            continue
        if player == bettor:
            if action_type in CALL_TYPES | BET_TYPES | RAISE_TYPES:
                break
            continue
        if action_type not in (CALL_TYPES | BET_TYPES | RAISE_TYPES):
            continue
        if player in seen_players:
            continue

        responder_cards = player_hole_cards.get(player, [])
        if not (
            responder_cards
            and flop_cards
            and len(responder_cards) == 2
            and len(flop_cards) == 3
        ):
            continue

        classification = classify_flop_hand(responder_cards, flop_cards)
        hand_primary = classification.primary
        if not hand_primary:
            continue

        responses.append(
            {
                "player": player,
                "response": "call" if action_type in CALL_TYPES else "raise",
                "hand_primary": hand_primary,
                "has_flush_draw": classification.has_flush_draw,
                "has_oesd_dg": classification.has_oesd_dg,
                "hole_cards": " ".join(card for _, _, card in responder_cards),
            }
        )
        seen_players.add(player)

    return responses
