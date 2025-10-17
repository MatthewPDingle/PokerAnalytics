from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from analysis.sqlite_utils import connect_readonly

from analysis.cbet_utils import (
    BASE_PRIMARY_CATEGORIES,
    BET_TYPES,
    CALL_TYPES,
    FOLD_TYPES,
    RAISE_TYPES,
    classify_hand,
    extract_big_blind,
    parse_cards_text,
)

TURN_BUCKETS: List[Tuple[float, float, str]] = [
    (0.00, 0.25, "[0.00, 0.25)"),
    (0.25, 0.40, "[0.25, 0.40)"),
    (0.40, 0.60, "[0.40, 0.60)"),
    (0.60, 0.80, "[0.60, 0.80)"),
    (0.80, 1.00, "[0.80, 1.00)"),
    (1.00, 1.25, "[1.00, 1.25)"),
    (1.25, float("inf"), ">=1.25"),
]


def _bucketize_ratio(amount: float, pot_before: float) -> float:
    if pot_before <= 0:
        return 0.0
    return round(amount / pot_before, 6)


def load_turn_events(
    db_path: Path,
    cache_path: Path | None = None,
    force: bool = False,
) -> List[Dict]:
    if cache_path and cache_path.exists() and not force:
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached and "line_type" in cached[0]:
            return cached

    events: List[Dict] = []

    with connect_readonly(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories")
        for row in cur:
            try:
                root = ET.fromstring(row["HandHistory"])
            except ET.ParseError:
                continue

            big_blind = extract_big_blind(root)
            if big_blind is None or big_blind <= 0:
                continue

            pocket_cards: Dict[str, List[Tuple[str, int, str]]] = {}
            for node in root.findall('.//round[@no="1"]/cards'):
                player = node.attrib.get("player")
                cards = parse_cards_text(node.text)
                if player and len(cards) == 2:
                    pocket_cards[player] = cards
            if not pocket_cards:
                continue

            flop_cards: List[Tuple[str, int, str]] | None = None
            turn_cards: List[Tuple[str, int, str]] | None = None
            total_pot = 0.0
            flop_bettors: set[str] = set()
            flop_bet_occurred = False
            flop_players: set[str] = set()
            flop_bet_ratio: Dict[str, float] = {}

            turn_actions: List[Tuple[str, str]] = []
            turn_players: set[str] = set()
            current_event: Dict | None = None
            responders_recorded: set[str] = set()
            turn_first_bettor: str | None = None

            rounds = sorted(root.findall(".//round"), key=lambda r: int(r.attrib.get("no", "0")))
            for rnd in rounds:
                round_no = int(rnd.attrib.get("no", "0"))

                if round_no == 2 and flop_cards is None:
                    for card_node in rnd.findall("cards"):
                        if card_node.attrib.get("type") == "Flop":
                            flop_cards = parse_cards_text(card_node.text)
                            break
                if round_no == 3 and turn_cards is None:
                    for card_node in rnd.findall("cards"):
                        if card_node.attrib.get("type") in {"Turn", "Board"}:
                            turn_cards = (flop_cards or []) + parse_cards_text(card_node.text)
                            break

                for action in rnd.findall("action"):
                    player = action.attrib.get("player")
                    if not player:
                        continue
                    act_type = action.attrib.get("type")
                    try:
                        amount = float(action.attrib.get("sum") or 0.0)
                    except ValueError:
                        amount = 0.0

                    if round_no == 2:
                        flop_players.add(player)
                        if act_type in BET_TYPES.union(RAISE_TYPES) and amount > 0:
                            pot_before = total_pot if total_pot > 0 else 0.0
                            ratio = amount / pot_before if pot_before else 0.0
                            flop_bettors.add(player)
                            flop_bet_ratio[player] = round(ratio, 6)
                            flop_bet_occurred = True
                    elif round_no == 3:
                        turn_players.add(player)
                        turn_actions.append((player, act_type))

                        if (
                            turn_first_bettor is None
                            and act_type in BET_TYPES.union(RAISE_TYPES)
                            and amount > 0
                        ):
                            if turn_cards is None:
                                continue
                            board_cards = turn_cards
                            hero_cards = pocket_cards.get(player)
                            if hero_cards is None:
                                continue

                            classification = classify_hand(hero_cards, board_cards)
                            ratio = _bucketize_ratio(amount, total_pot)
                            is_all_in = act_type == "7"
                            bet_amount = amount
                            bet_amount_bb = bet_amount / big_blind if big_blind else None
                            tolerance = max(1e-6, (big_blind or 0.0) * 1e-4)
                            is_one_bb = bool(big_blind) and abs(bet_amount - big_blind) <= tolerance
                            event = {
                                "hand_number": row["HandNumber"],
                                "player": player,
                                "ratio": ratio,
                                "line_type": "Barrel" if player in flop_bettors else ("Delayed" if not flop_bet_occurred else "Other"),
                                "primary": classification["primary"],
                                "has_flush_draw": bool(classification["flush_draw"]),
                                "has_oesd_dg": bool(classification["oesd_dg"]),
                                "made_flush": bool(classification["made_flush"]),
                                "made_straight": bool(classification["made_straight"]),
                                "made_full_house": bool(classification["made_full"]),
                                "hole_cards": " ".join(card for _, _, card in hero_cards),
                                "board": " ".join(card for _, _, card in board_cards),
                                "flop_board": " ".join(card for _, _, card in (flop_cards or [])),
                                "turn_card": board_cards[-1][2] if len(board_cards) >= 4 else "",
                                "responses": [],
                                "bettor_in_position": any(actor != player for actor, _ in turn_actions[:-1]),
                                "flop_players": len(flop_players) if flop_players else 0,
                                "turn_players": len(turn_players),
                                "bet_amount": bet_amount,
                                "bet_amount_bb": bet_amount_bb,
                                "bet_action_type": act_type,
                                "is_all_in": is_all_in,
                                "is_one_bb": is_one_bb,
                                "big_blind": big_blind,
                                "pot_before": total_pot,
                                "flop_ratio": flop_bet_ratio.get(player),
                            }
                            events.append(event)
                            current_event = event
                            responders_recorded = set()
                            turn_first_bettor = player

                        elif (
                            current_event is not None
                            and player != current_event["player"]
                            and player not in responders_recorded
                        ):
                            response_kind: str | None = None
                            if act_type in FOLD_TYPES:
                                response_kind = "Fold"
                            elif act_type in CALL_TYPES:
                                response_kind = "Call"
                            elif act_type in RAISE_TYPES:
                                response_kind = "Raise"
                            elif act_type in BET_TYPES:
                                response_kind = "Raise"

                            if response_kind:
                                hero_cards = pocket_cards.get(player)
                                classification = None
                                if hero_cards is not None and turn_cards is not None:
                                    classification = classify_hand(hero_cards, turn_cards)
                                current_event["responses"].append(
                                    {
                                        "player": player,
                                        "response": response_kind,
                                        "action_type": act_type,
                                        "amount": amount,
                                        "primary": classification["primary"] if classification else None,
                                        "has_flush_draw": bool(classification["flush_draw"]) if classification else False,
                                        "has_oesd_dg": bool(classification["oesd_dg"]) if classification else False,
                                        "made_flush": bool(classification["made_flush"]) if classification else False,
                                        "made_straight": bool(classification["made_straight"]) if classification else False,
                                        "made_full_house": bool(classification["made_full"]) if classification else False,
                                    }
                                )
                                responders_recorded.add(player)

                        if current_event is not None:
                            current_event["turn_players"] = len(turn_players)

                    if amount > 0:
                        total_pot += amount

                if round_no != 3:
                    current_event = None

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(events, fh, ensure_ascii=False, indent=2)

    return events


def load_turn_first_actions(
    db_path: Path,
    cache_path: Path | None = None,
    force: bool = False,
) -> List[Dict]:
    if cache_path and cache_path.exists() and not force:
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached and "action_kind" in cached[0]:
            return cached

    records: List[Dict] = []

    with connect_readonly(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories")
        for row in cur:
            try:
                root = ET.fromstring(row["HandHistory"])
            except ET.ParseError:
                continue

            big_blind = extract_big_blind(root)
            if big_blind is None or big_blind <= 0:
                continue

            pocket_cards: Dict[str, List[Tuple[str, int, str]]] = {}
            for node in root.findall('.//round[@no="1"]/cards'):
                player = node.attrib.get("player")
                cards = parse_cards_text(node.text)
                if player and len(cards) == 2:
                    pocket_cards[player] = cards
            if not pocket_cards:
                continue

            flop_cards: List[Tuple[str, int, str]] | None = None
            turn_cards: List[Tuple[str, int, str]] | None = None
            total_pot = 0.0

            turn_first_actions: Dict[str, Dict] = {}
            action_order: List[str] = []
            first_bet_player: str | None = None

            rounds = sorted(root.findall(".//round"), key=lambda r: int(r.attrib.get("no", "0")))
            for rnd in rounds:
                round_no = int(rnd.attrib.get("no", "0"))

                if round_no == 2 and flop_cards is None:
                    for card_node in rnd.findall("cards"):
                        if card_node.attrib.get("type") == "Flop":
                            flop_cards = parse_cards_text(card_node.text)
                            break
                if round_no == 3 and turn_cards is None:
                    for card_node in rnd.findall("cards"):
                        if card_node.attrib.get("type") in {"Turn", "Board"}:
                            turn_cards = (flop_cards or []) + parse_cards_text(card_node.text)
                            break

                for action in rnd.findall("action"):
                    player = action.attrib.get("player")
                    if not player:
                        continue
                    act_type = action.attrib.get("type")
                    try:
                        amount = float(action.attrib.get("sum") or 0.0)
                    except ValueError:
                        amount = 0.0

                    if round_no == 3:
                        if player not in turn_first_actions:
                            pot_before = total_pot
                            action_kind: str
                            if act_type in BET_TYPES:
                                action_kind = "all-in" if act_type == "7" else "bet"
                            elif act_type == "4" and amount == 0:
                                action_kind = "check"
                            elif act_type in CALL_TYPES:
                                action_kind = "call"
                            elif act_type in RAISE_TYPES:
                                action_kind = "raise"
                            elif act_type == "0":
                                action_kind = "fold"
                            else:
                                action_kind = "other"

                            order = len(action_order) + 1
                            ratio = None
                            bet_amount_bb = None
                            is_all_in = False
                            is_one_bb = False
                            if action_kind in {"bet", "all-in"} and amount > 0:
                                ratio = amount / pot_before if pot_before > 0 else None
                                bet_amount_bb = amount / big_blind if big_blind else None
                                is_all_in = action_kind == "all-in"
                                tolerance = max(1e-6, (big_blind or 0.0) * 1e-4)
                                is_one_bb = bool(big_blind) and abs(amount - big_blind) <= tolerance
                            turn_first_actions[player] = {
                                "action_kind": action_kind,
                                "raw_type": act_type,
                                "amount": amount,
                                "order": order,
                                "pot_before": pot_before,
                                "ratio": round(ratio, 6) if ratio is not None else None,
                                "bet_amount_bb": bet_amount_bb,
                                "is_all_in": is_all_in,
                                "is_one_bb": is_one_bb,
                            }
                            action_order.append(player)
                            if action_kind in {"bet", "all-in"} and first_bet_player is None:
                                first_bet_player = player

                    if amount > 0:
                        total_pot += amount

            if turn_cards is None or not turn_first_actions:
                continue

            max_order = max(data["order"] for data in turn_first_actions.values())
            first_bet_order: int | None = None
            considered_players: List[str]
            first_bet_present = first_bet_player is not None
            if first_bet_player is not None:
                first_bet_order = turn_first_actions[first_bet_player]["order"]
                considered_players = [
                    player for player in action_order if turn_first_actions[player]["order"] <= first_bet_order
                ]
            else:
                considered_players = list(action_order)

            for player in considered_players:
                cards = pocket_cards.get(player)
                if cards is None:
                    continue
                classification = classify_hand(cards, turn_cards)
                data = turn_first_actions[player]
                order = data["order"]
                if first_bet_present:
                    in_position = bool(first_bet_order is not None and order == first_bet_order and order == max_order)
                else:
                    in_position = order == max_order

                record = {
                    "hand_number": row["HandNumber"],
                    "player": player,
                    "primary": classification["primary"],
                    "has_flush_draw": bool(classification["flush_draw"]),
                    "has_oesd_dg": bool(classification["oesd_dg"]),
                    "made_flush": bool(classification["made_flush"]),
                    "made_straight": bool(classification["made_straight"]),
                    "made_full_house": bool(classification["made_full"]),
                    "action_kind": data["action_kind"],
                    "raw_action_type": data["raw_type"],
                    "bet_flag": data["action_kind"] in {"bet", "all-in"},
                    "is_all_in": data["is_all_in"],
                    "is_one_bb": data["is_one_bb"],
                    "amount": data["amount"],
                    "pot_before": data["pot_before"],
                    "ratio": data["ratio"],
                    "bet_amount_bb": data["bet_amount_bb"],
                    "order": order,
                    "players_on_turn": max_order,
                    "first_bet_present": first_bet_present,
                    "first_bet_player": first_bet_player,
                    "in_position": in_position,
                    "hole_cards": " ".join(card for _, _, card in cards),
                    "board": " ".join(card for _, _, card in turn_cards),
                    "flop_board": " ".join(card for _, _, card in (flop_cards or [])),
                    "turn_card": turn_cards[-1][2] if len(turn_cards) >= 4 else "",
                    "big_blind": big_blind,
                }
                records.append(record)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)

    return records


def turn_response_events(events: List[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for event in events:
        responses = event.get("responses") or []
        total_responses = len(responses)
        for order, response in enumerate(responses, start=1):
            rows.append(
                {
                    "hand_number": event.get("hand_number"),
                    "bettor": event.get("player"),
                    "ratio": event.get("ratio"),
                    "line_type": event.get("line_type"),
                    "responder": response.get("player"),
                    "response": response.get("response"),
                    "response_order": order,
                    "response_amount": response.get("amount"),
                    "responses_recorded": total_responses,
                    "bettor_in_position": event.get("bettor_in_position"),
                    "responder_primary": response.get("primary"),
                    "responder_has_flush_draw": bool(response.get("has_flush_draw")),
                    "responder_has_oesd_dg": bool(response.get("has_oesd_dg")),
                    "responder_made_flush": bool(response.get("made_flush")),
                    "responder_made_straight": bool(response.get("made_straight")),
                    "responder_made_full_house": bool(response.get("made_full_house")),
                    "is_all_in_bet": bool(event.get("is_all_in")),
                    "is_one_bb_bet": bool(event.get("is_one_bb")),
                }
            )
    return rows


def available_primary_categories(events: List[Dict]) -> List[str]:
    return sorted({event["primary"] for event in events})
