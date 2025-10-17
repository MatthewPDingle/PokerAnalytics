from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
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


RIVER_BUCKET_BOUNDS: List[Tuple[float, float]] = [
    (0.00, 0.25),
    (0.25, 0.40),
    (0.40, 0.60),
    (0.60, 0.80),
    (0.80, 1.00),
    (1.00, 1.25),
    (1.25, float("inf")),
]


def _bucket_label(low: float, high: float) -> str:
    if high == float("inf"):
        return f">={low:.2f}"
    return f"[{low:.2f}, {high:.2f})"


RIVER_BUCKETS: List[Tuple[float, float, str]] = [
    (low, high, _bucket_label(low, high))
    for low, high in RIVER_BUCKET_BOUNDS
]


def _ratio(amount: float, pot_before: float) -> float:
    if pot_before <= 0:
        return 0.0
    return round(amount / pot_before, 6)


def load_river_events(
    db_path: Path,
    cache_path: Path | None = None,
    force: bool = False,
) -> List[Dict]:
    if cache_path and cache_path.exists() and not force:
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached and "line_type" in cached[0] and "missed_draw" in cached[0]:
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
            river_cards: List[Tuple[str, int, str]] | None = None

            total_pot = 0.0
            flop_bettors: set[str] = set()
            turn_bettors: set[str] = set()

            river_actions: List[Tuple[str, str]] = []
            river_players: set[str] = set()
            current_event: Dict | None = None
            responders_recorded: set[str] = set()

            rounds = sorted(root.findall('.//round'), key=lambda r: int(r.attrib.get('no', '0')))
            for rnd in rounds:
                round_no = int(rnd.attrib.get('no', '0'))

                if round_no == 2 and flop_cards is None:
                    for card_node in rnd.findall('cards'):
                        if card_node.attrib.get('type') == 'Flop':
                            flop_cards = parse_cards_text(card_node.text)
                            break
                if round_no == 3 and turn_cards is None:
                    for card_node in rnd.findall('cards'):
                        if card_node.attrib.get('type') in {'Turn', 'Board'}:
                            turn_cards = (flop_cards or []) + parse_cards_text(card_node.text)
                            break
                if round_no == 4:
                    for card_node in rnd.findall('cards'):
                        if card_node.attrib.get('type') in {'River', 'Board'}:
                            river_cards = (turn_cards or []) + parse_cards_text(card_node.text)
                            break

                for action in rnd.findall('action'):
                    player = action.attrib.get('player')
                    if not player:
                        continue
                    act_type = action.attrib.get('type')
                    try:
                        amount = float(action.attrib.get('sum') or 0.0)
                    except ValueError:
                        amount = 0.0

                    if round_no == 2:
                        if act_type in BET_TYPES.union(RAISE_TYPES) and amount > 0:
                            flop_bettors.add(player)
                    if round_no == 3:
                        if act_type in BET_TYPES.union(RAISE_TYPES) and amount > 0:
                            turn_bettors.add(player)

                    if round_no == 4:
                        river_players.add(player)
                        river_actions.append((player, act_type))

                        if (
                            current_event is None
                            and act_type in BET_TYPES.union(RAISE_TYPES)
                            and amount > 0
                        ):
                            if river_cards is None:
                                continue
                            hero_cards = pocket_cards.get(player)
                            if hero_cards is None:
                                continue

                            classification = classify_hand(hero_cards, river_cards)
                            primary = classification["primary"]

                            flop_draw_flush = False
                            flop_draw_oesd_dg = False
                            if flop_cards:
                                flop_class = classify_hand(hero_cards, flop_cards)
                                if not flop_class["made_flush"] and flop_class["flush_draw"]:
                                    flop_draw_flush = True
                                if not flop_class["made_straight"] and flop_class["oesd_dg"]:
                                    flop_draw_oesd_dg = True

                            turn_draw_flush = False
                            turn_draw_oesd_dg = False
                            if turn_cards:
                                turn_class = classify_hand(hero_cards, turn_cards)
                                if not turn_class["made_flush"] and turn_class["flush_draw"]:
                                    turn_draw_flush = True
                                if not turn_class["made_straight"] and turn_class["oesd_dg"]:
                                    turn_draw_oesd_dg = True

                            had_flop_draw = flop_draw_flush or flop_draw_oesd_dg
                            had_turn_draw = turn_draw_flush or turn_draw_oesd_dg
                            had_draw = had_flop_draw or had_turn_draw
                            draw_completed = classification["made_flush"] or classification["made_straight"]
                            missed_draw = had_draw and not draw_completed

                            has_flush_draw = False
                            has_oesd_dg = bool(classification['oesd_dg'])

                            if player in flop_bettors and player in turn_bettors:
                                line_type = 'Triple Barrel'
                            elif player not in flop_bettors and player in turn_bettors:
                                line_type = 'Turn Follow-up'
                            elif player in flop_bettors and player not in turn_bettors:
                                line_type = 'Flop-River'
                            elif player not in flop_bettors and player not in turn_bettors:
                                line_type = 'River Only'
                            else:
                                line_type = 'Other'

                            ratio = _ratio(amount, total_pot)
                            pot_before = total_pot
                            bet_amount = amount
                            bet_amount_bb = bet_amount / big_blind if big_blind else None
                            tolerance = max(1e-6, (big_blind or 0.0) * 1e-4)
                            is_one_bb = bool(big_blind) and abs(bet_amount - (big_blind or 0.0)) <= tolerance
                            is_all_in = act_type == '7'

                            event = {
                                'hand_number': row['HandNumber'],
                                'player': player,
                                'ratio': ratio,
                                'bet_amount': bet_amount,
                                'bet_amount_bb': bet_amount_bb,
                                'big_blind': big_blind,
                                'pot_before': pot_before,
                                'is_all_in': is_all_in,
                                'is_one_bb': is_one_bb,
                                'line_type': line_type,
                                'primary': primary,
                                'has_flush_draw': has_flush_draw,
                                'has_oesd_dg': has_oesd_dg,
                                'missed_draw': missed_draw,
                                'had_flop_draw': had_flop_draw,
                                'had_turn_draw': had_turn_draw,
                                'had_pre_river_draw': had_draw,
                                'had_flop_flush_draw': flop_draw_flush,
                                'had_flop_oesd_dg': flop_draw_oesd_dg,
                                'had_turn_flush_draw': turn_draw_flush,
                                'had_turn_oesd_dg': turn_draw_oesd_dg,
                                'made_flush': bool(classification['made_flush']),
                                'made_straight': bool(classification['made_straight']),
                                'made_full_house': bool(classification['made_full']),
                                'hole_cards': ' '.join(card for _, _, card in hero_cards),
                                'board': ' '.join(card for _, _, card in river_cards),
                                'responses': [],
                                'bettor_in_position': any(actor != player for actor, _ in river_actions[:-1]),
                            }
                            events.append(event)
                            current_event = event
                            responders_recorded = set()

                        elif (
                            current_event is not None
                            and player != current_event['player']
                            and player not in responders_recorded
                        ):
                            response_kind: str | None = None
                            if act_type in FOLD_TYPES:
                                response_kind = 'Fold'
                            elif act_type in CALL_TYPES:
                                response_kind = 'Call'
                            elif act_type in RAISE_TYPES:
                                response_kind = 'Raise'
                            elif act_type in BET_TYPES:
                                response_kind = 'Raise'

                            if response_kind:
                                hero_cards = pocket_cards.get(player)
                                classification = None
                                responder_primary = None
                                missed_draw = False
                                if hero_cards is not None and river_cards is not None:
                                    classification = classify_hand(hero_cards, river_cards)
                                    responder_primary = classification['primary']
                                    if responder_primary == 'Air' and (classification['flush_draw'] or classification['oesd_dg']):
                                        missed_draw = True
                                current_event['responses'].append(
                                    {
                                        'player': player,
                                        'response': response_kind,
                                        'action_type': act_type,
                                        'amount': amount,
                                        'primary': responder_primary,
                                        'has_flush_draw': False,
                                        'has_oesd_dg': False,
                                        'missed_draw': missed_draw,
                                        'made_flush': bool(classification['made_flush']) if classification else False,
                                        'made_straight': bool(classification['made_straight']) if classification else False,
                                        'made_full_house': bool(classification['made_full']) if classification else False,
                                    }
                                )
                                responders_recorded.add(player)

                    if amount > 0:
                        total_pot += amount

                if round_no != 4:
                    current_event = None

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open('w', encoding='utf-8') as fh:
            json.dump(events, fh, ensure_ascii=False, indent=2)

    return events


def river_response_events(events: List[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for event in events:
        responses = event.get('responses') or []
        total = len(responses)
        for order, response in enumerate(responses, start=1):
            rows.append(
                {
                    'hand_number': event.get('hand_number'),
                    'bettor': event.get('player'),
                    'ratio': event.get('ratio'),
                    'line_type': event.get('line_type'),
                    'bettor_missed_draw': event.get('missed_draw'),
                    'bettor_had_flop_draw': event.get('had_flop_draw'),
                    'bettor_had_turn_draw': event.get('had_turn_draw'),
                    'bettor_had_pre_river_draw': event.get('had_pre_river_draw'),
                    'responder': response.get('player'),
                    'response': response.get('response'),
                    'response_order': order,
                    'response_amount': response.get('amount'),
                    'responses_recorded': total,
                    'bettor_in_position': event.get('bettor_in_position'),
                    'responder_primary': response.get('primary'),
                    'responder_has_flush_draw': False,
                    'responder_has_oesd_dg': False,
                    'responder_missed_draw': bool(response.get('missed_draw')),
                    'responder_made_flush': bool(response.get('made_flush')),
                    'responder_made_straight': bool(response.get('made_straight')),
                    'responder_made_full_house': bool(response.get('made_full_house')),
                }
            )
    return rows


def available_primary_categories(events: Sequence[Dict]) -> List[str]:
    return sorted({event['primary'] for event in events})
