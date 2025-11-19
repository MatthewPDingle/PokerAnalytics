
#!/usr/bin/env python3
"""Monte Carlo equity calculator for preflop shove ranges."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import random
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

SUIT_MAP_INPUT = {
    'S': 's', 'H': 'h', 'D': 'd', 'C': 'c',
    's': 's', 'h': 'h', 'd': 'd', 'c': 'c',
}
RANK_CHARS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_TO_VALUE = {r: i for i, r in enumerate(RANK_CHARS)}
RANKS_DESC = list(reversed(RANK_CHARS))

CATEGORY_LABELS = {
    1: 'First to Bet Shove',
    2: '3-Bet Shove',
    3: '4-Bet Shove',
    4: '5+ Bet Shove',
}

SCENARIOS = {
    'first_to_bet_leq30': (
        'First to Bet Shove (≤30 BB)',
        lambda row: row['category'] == 'First to Bet Shove' and row.get('bet_amount_bb') is not None and row['bet_amount_bb'] <= 30.0,
    ),
    'first_to_bet_gt30': (
        'First to Bet Shove (>30 BB)',
        lambda row: row['category'] == 'First to Bet Shove' and row.get('bet_amount_bb') is not None and row['bet_amount_bb'] > 30.0,
    ),
    'three_bet_shove': (
        '3-Bet Shove',
        lambda row: row['category'] == '3-Bet Shove',
    ),
    'four_bet_shove': (
        '4-Bet Shove',
        lambda row: row['category'] == '4-Bet Shove',
    ),
    'five_plus_bet_shove': (
        '5+ Bet Shove',
        lambda row: row['category'] == '5+ Bet Shove',
    ),
}

SUITS = ['s', 'h', 'd', 'c']

SCENARIO_ASSUMPTIONS = {
    'first_to_bet_leq30': {'effective_stack_bb': 20.0},
    'first_to_bet_gt30': {'effective_stack_bb': 100.0},
    'three_bet_shove': {'effective_stack_bb': 100.0},
    'four_bet_shove': {'effective_stack_bb': 100.0},
    'five_plus_bet_shove': {'effective_stack_bb': 100.0},
}


def card_to_str(card: str) -> str:
    """Convert repository card format (SuitRank or RankSuit) to 'Rs' format."""
    card = card.strip()
    if len(card) != 2:
        raise ValueError(f'Unexpected card format: {card!r}')
    first, second = card[0], card[1]
    first_up = first.upper()
    second_up = second.upper()
    if first_up in SUIT_MAP_INPUT and second_up in RANK_TO_VALUE:
        rank = second_up
        suit = SUIT_MAP_INPUT[first]
        return rank + suit
    if second_up in SUIT_MAP_INPUT and first_up in RANK_TO_VALUE:
        rank = first_up
        suit = SUIT_MAP_INPUT[second]
        return rank + suit
    raise ValueError(f'Unable to parse card string: {card!r}')


def load_preflop_shove_events(db_path: Path) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories')
        for row in cur:
            try:
                root = ET.fromstring(row['HandHistory'])
            except ET.ParseError:
                continue

            big_blind = extract_big_blind(root)
            if big_blind is None or big_blind <= 0:
                continue

            pocket_cards: Dict[str, List[str]] = {}
            for node in root.findall('.//round[@no="1"]/cards'):
                player = node.attrib.get('player')
                cards = parse_cards_text(node.text)
                if player and len(cards) == 2:
                    pocket_cards[player] = cards
            if not pocket_cards:
                continue

            player_contrib: Counter[str] = Counter()
            total_pot = 0.0

            for action in root.findall('.//round[@no="0"]/action'):
                player = action.attrib.get('player')
                if not player:
                    continue
                amount_text = action.attrib.get('sum') or action.attrib.get('bet')
                if not amount_text:
                    continue
                try:
                    amount_total = float(amount_text)
                except ValueError:
                    continue
                prev = player_contrib[player]
                delta = max(amount_total - prev, 0.0)
                if delta <= 0:
                    continue
                player_contrib[player] = amount_total
                total_pot += delta

            aggressive_level = 0

            preflop_actions = []
            for rnd in root.findall('.//round'):
                if rnd.attrib.get('no') == '1':
                    preflop_actions.extend(rnd.findall('action'))

            for action in preflop_actions:
                player = action.attrib.get('player')
                if not player:
                    continue
                act_type = action.attrib.get('type')
                amount_text = action.attrib.get('sum') or action.attrib.get('bet') or '0'
                try:
                    amount_total = float(amount_text)
                except ValueError:
                    amount_total = 0.0

                prev = player_contrib[player]
                delta = max(amount_total - prev, 0.0)
                if delta <= 0:
                    continue

                pot_before = total_pot
                total_pot += delta
                player_contrib[player] = prev + delta

                if act_type not in BET_TYPES.union(RAISE_TYPES):
                    continue
                aggressive_level += 1
                if not is_all_in_action(action):
                    continue

                category = categorise_shove(aggressive_level)
                if category is None:
                    continue
                hero_cards = pocket_cards.get(player)
                if not hero_cards:
                    continue
                try:
                    hole_cards = ' '.join(card_to_str(card) for card in hero_cards)
                except ValueError:
                    continue
                events.append({
                    'hand_number': row['HandNumber'],
                    'player': player,
                    'category': category,
                    'aggressive_level': aggressive_level,
                    'hole_cards': hole_cards,
                    'bet_amount': amount_total,
                    'bet_amount_bb': amount_total / big_blind if big_blind else None,
                    'bet_amount_added': delta,
                    'bet_amount_added_bb': delta / big_blind if big_blind else None,
                    'pot_before': pot_before,
                    'big_blind': big_blind,
                })
    return events


BET_TYPES = {'5', '7'}
RAISE_TYPES = {'23', '7'}


def parse_cards_text(text: str | None) -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.split() if p.strip()]
    return parts


import re

BB_PATTERN = re.compile(r"\$(\d+(?:\.\d+)?)/?(\d+(?:\.\d+)?)?")


def extract_big_blind(root: ET.Element) -> float | None:
    for xpath in ("./general/gametype", ".//game/general/gametype"):
        node = root.find(xpath)
        if node is not None and node.text:
            match = BB_PATTERN.search(node.text)
            if match:
                try:
                    return float(match.group(2) or match.group(1))
                except ValueError:
                    pass
    for xpath in ("./general/bigblind", ".//game/general/bigblind"):
        node = root.find(xpath)
        if node is not None and node.text:
            try:
                return float(node.text)
            except ValueError:
                pass
    return None


def categorise_shove(level: int) -> str | None:
    if level <= 0:
        return None
    return CATEGORY_LABELS.get(level, CATEGORY_LABELS[4])


def is_all_in_action(action: ET.Element) -> bool:
    act_type = action.attrib.get('type')
    if act_type == '7':
        return True
    return action.attrib.get('allin', '').lower() in {'1', 'true', 'yes'}


def combo_from_string(card_string: str) -> Tuple[str, str]:
    cards = card_string.split()
    if len(cards) != 2:
        raise ValueError(f'Unexpected combo format: {card_string!r}')
    return tuple(sorted(cards))


def generate_cell_combos(row_rank: str, col_rank: str) -> List[Tuple[str, str]]:
    row_idx = RANKS_DESC.index(row_rank)
    col_idx = RANKS_DESC.index(col_rank)
    combos: List[Tuple[str, str]] = []
    if row_rank == col_rank:
        for i in range(len(SUITS)):
            for j in range(i + 1, len(SUITS)):
                combos.append((f"{row_rank}{SUITS[i]}", f"{col_rank}{SUITS[j]}"))
    elif row_idx < col_idx:
        # suited combos (row higher rank)
        for suit in SUITS:
            combos.append((f"{row_rank}{suit}", f"{col_rank}{suit}"))
    else:
        # offsuit combos
        for suit1 in SUITS:
            for suit2 in SUITS:
                if suit1 == suit2:
                    continue
                combos.append((f"{row_rank}{suit1}", f"{col_rank}{suit2}"))
    # normalise order (sorted)
    combos = [tuple(sorted(combo)) for combo in combos]
    return combos


def evaluate_5(cards: Sequence[str]) -> Tuple[int, List[int]]:
    ranks = [card[0] for card in cards]
    suits = [card[1] for card in cards]
    values = sorted((RANK_TO_VALUE[r] for r in ranks), reverse=True)
    counts = Counter(ranks)
    counts_by_rank = sorted(counts.items(), key=lambda item: (item[1], RANK_TO_VALUE[item[0]]), reverse=True)
    is_flush = len(set(suits)) == 1

    unique_values = sorted({RANK_TO_VALUE[r] for r in ranks}, reverse=True)
    is_straight = False
    straight_high = -1
    if len(unique_values) == 5:
        if unique_values[0] - unique_values[4] == 4:
            is_straight = True
            straight_high = unique_values[0]
        elif unique_values == [12, 3, 2, 1, 0]:  # A2345 straight
            is_straight = True
            straight_high = 3

    if is_straight and is_flush:
        return 8, [straight_high]
    if counts_by_rank[0][1] == 4:
        four_value = RANK_TO_VALUE[counts_by_rank[0][0]]
        kicker = max(v for v in values if v != four_value)
        return 7, [four_value, kicker]
    if counts_by_rank[0][1] == 3 and counts_by_rank[1][1] == 2:
        triple_value = RANK_TO_VALUE[counts_by_rank[0][0]]
        pair_value = RANK_TO_VALUE[counts_by_rank[1][0]]
        return 6, [triple_value, pair_value]
    if is_flush:
        return 5, values
    if is_straight:
        return 4, [straight_high]
    if counts_by_rank[0][1] == 3:
        triple_value = RANK_TO_VALUE[counts_by_rank[0][0]]
        kickers = [RANK_TO_VALUE[counts_by_rank[i][0]] for i in range(1, len(counts_by_rank)) for _ in range(counts_by_rank[i][1])]
        return 3, [triple_value] + sorted(kickers, reverse=True)
    if counts_by_rank[0][1] == 2 and counts_by_rank[1][1] == 2:
        pair_values = [RANK_TO_VALUE[counts_by_rank[i][0]] for i in range(2) if counts_by_rank[i][1] == 2]
        pair_values.sort(reverse=True)
        kicker = max(v for v in values if v not in pair_values)
        return 2, pair_values + [kicker]
    if counts_by_rank[0][1] == 2:
        pair_value = RANK_TO_VALUE[counts_by_rank[0][0]]
        kickers = [RANK_TO_VALUE[counts_by_rank[i][0]] for i in range(1, len(counts_by_rank)) for _ in range(counts_by_rank[i][1])]
        return 1, [pair_value] + sorted(kickers, reverse=True)
    return 0, values


def evaluate_7(cards: Sequence[str]) -> Tuple[int, List[int]]:
    best: Tuple[int, List[int]] | None = None
    for combo in combinations(cards, 5):
        score = evaluate_5(combo)
        if best is None or score > best:
            best = score
    assert best is not None
    return best


def weighted_choice(options: List[Tuple[Tuple[str, str], float]], total_weight: float, rng: random.Random) -> Tuple[str, str]:
    pick = rng.random() * total_weight
    cumulative = 0.0
    for combo, weight in options:
        cumulative += weight
        if pick <= cumulative:
            return combo
    return options[-1][0]


def prepare_villain_data(villain_weights: Dict[Tuple[str, str], int], hero_combos: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], Tuple[List[Tuple[Tuple[str, str], float]], float]]:
    data: Dict[Tuple[str, str], Tuple[List[Tuple[Tuple[str, str], float]], float]] = {}
    for hero_combo in hero_combos:
        hero_cards = set(hero_combo)
        options: List[Tuple[Tuple[str, str], float]] = []
        total_weight = 0.0
        for combo, weight in villain_weights.items():
            if hero_cards.intersection(combo):
                continue
            total_weight += weight
            options.append((combo, float(weight)))
        data[hero_combo] = (options, total_weight)
    return data



def simulate_cell_worker(task: Tuple[str, str, List[Tuple[str, str]], List[Tuple[Tuple[str, str], int]], int, int]) -> Tuple[str, str, float, Dict[str, float]]:
    row_rank, col_rank, hero_combos_raw, villain_weights_raw, trials_per_combo, seed = task
    rng = random.Random(seed)

    hero_combos = [tuple(combo) for combo in hero_combos_raw]
    villain_weights = {tuple(combo): weight for combo, weight in villain_weights_raw}

    hero_stats: Dict[Tuple[str, str], Dict[str, float]] = {
        combo: {'wins': 0.0, 'ties': 0.0, 'total': 0.0}
        for combo in hero_combos
    }

    villain_data = prepare_villain_data(villain_weights, hero_combos)
    if not villain_data:
        return row_rank, col_rank, math.nan, {}

    deck = [rank + suit for rank in RANK_CHARS for suit in SUITS]

    for combo in hero_combos:
        options, total_weight = villain_data[combo]
        if total_weight <= 0.0:
            continue
        hero_cards = list(combo)
        for _ in range(trials_per_combo):
            villain_combo = weighted_choice(options, total_weight, rng)
            villain_cards = list(villain_combo)
            used_cards = set(hero_cards + villain_cards)
            remaining_deck = [card for card in deck if card not in used_cards]
            board = rng.sample(remaining_deck, 5)
            hero_score = evaluate_7(hero_cards + board)
            villain_score = evaluate_7(villain_cards + board)
            hero_stats[combo]['total'] += 1
            if hero_score > villain_score:
                hero_stats[combo]['wins'] += 1
            elif hero_score == villain_score:
                hero_stats[combo]['ties'] += 1

    combo_equities: Dict[str, float] = {}
    equity_sum = 0.0
    count = 0
    for combo, stats in hero_stats.items():
        total = stats['total']
        if total == 0:
            continue
        equity = (stats['wins'] + 0.5 * stats['ties']) / total * 100.0
        combo_key = ' '.join(sorted(combo))
        combo_equities[combo_key] = equity
        equity_sum += equity
        count += 1
    cell_equity = equity_sum / count if count else math.nan
    return row_rank, col_rank, cell_equity, combo_equities


def compute_scenario_equity(
    villain_weights: Dict[Tuple[str, str], int],
    trials: int,
    workers: int,
    seed: int,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    grid: Dict[str, Dict[str, float]] = {row: {col: math.nan for col in RANKS_DESC} for row in RANKS_DESC}
    combo_equities: Dict[str, float] = {}

    tasks = []
    villain_items = [(tuple(combo), weight) for combo, weight in villain_weights.items()]
    base_seed = seed
    task_idx = 0
    for row_rank in RANKS_DESC:
        for col_rank in RANKS_DESC:
            hero_combos = generate_cell_combos(row_rank, col_rank)
            if not hero_combos:
                continue
            trials_per_combo = max(trials // max(len(hero_combos), 1), 1)
            tasks.append((
                row_rank,
                col_rank,
                [tuple(combo) for combo in hero_combos],
                [(tuple(combo), weight) for combo, weight in villain_items],
                trials_per_combo,
                base_seed + task_idx,
            ))
            task_idx += 1

    if not tasks:
        return grid, combo_equities

    max_workers = min(max(workers, 1), len(tasks))

    def apply_result(result):
        row_rank, col_rank, cell_equity, combo_results = result
        grid[row_rank][col_rank] = None if math.isnan(cell_equity) else cell_equity
        combo_equities.update(combo_results)

    if max_workers <= 1:
        for task in tasks:
            apply_result(simulate_cell_worker(task))
        return grid, combo_equities

    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(simulate_cell_worker, tasks):
                apply_result(result)
    except (PermissionError, OSError):
        for task in tasks:
            apply_result(simulate_cell_worker(task))

    return grid, combo_equities


def build_villain_data(events: List[Dict[str, object]]) -> Tuple[Dict[str, Dict[Tuple[str, str], int]], Dict[str, Dict[str, float]]]:
    scenario_weights: Dict[str, Dict[Tuple[str, str], int]] = {key: Counter() for key in SCENARIOS}
    scenario_stats: Dict[str, Dict[str, float]] = {
        key: {'bet_sum': 0.0, 'bet_added_sum': 0.0, 'pot_sum': 0.0, 'count': 0}
        for key in SCENARIOS
    }
    for row in events:
        combo = tuple(sorted(card_to_str(card) for card in row['hole_cards'].split()))
        big_blind = row['big_blind']
        bet_bb = row['bet_amount'] / big_blind
        bet_added = row.get('bet_amount_added') or 0.0
        bet_added_bb = bet_added / big_blind
        pot_bb = row['pot_before'] / big_blind
        for key, (_, predicate) in SCENARIOS.items():
            if predicate(row):
                scenario_weights[key][combo] += 1
                scenario_stats[key]['bet_sum'] += bet_bb
                scenario_stats[key]['bet_added_sum'] += bet_added_bb
                scenario_stats[key]['pot_sum'] += pot_bb
                scenario_stats[key]['count'] += 1
    return scenario_weights, scenario_stats


def compute_ev_grid(
    equity_grid: Dict[str, Dict[str, float]],
    call_amount: float,
    villain_amount: float | None,
    pot_before: float,
    rake_percent: float = 0.05,
    rake_cap: float = 10.0,
) -> Dict[str, Dict[str, float]]:
    ev_grid: Dict[str, Dict[str, float]] = {row: {col: math.nan for col in RANKS_DESC} for row in RANKS_DESC}
    villain_amt = call_amount if villain_amount is None else float(villain_amount)
    final_pot = float(pot_before) + float(call_amount) + villain_amt
    rake = min(float(rake_percent) * final_pot, float(rake_cap))
    post_rake_pot = final_pot - rake
    for row in RANKS_DESC:
        for col in RANKS_DESC:
            equity = equity_grid.get(row, {}).get(col)
            if equity is None or math.isnan(equity):
                continue
            equity_dec = equity / 100.0
            ev = equity_dec * post_rake_pot - call_amount
            ev_grid[row][col] = ev
    return ev_grid


def main():
    parser = argparse.ArgumentParser(description='Precompute equity tables for shove ranges.')
    parser.add_argument(
        '--database',
        type=Path,
        default=Path('drivehud/drivehud.db'),
        help='Path to DriveHUD SQLite database.',
    )
    parser.add_argument(
        '--events-json',
        type=Path,
        default=None,
        help='Optional path to a JSON file with preflop shove events (overrides --database when provided).',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('analysis/cache/preflop_equity.json'),
        help='Output JSON path for equity results.',
    )
    parser.add_argument(
        '--trials',
        type=int,
        default=20000,
        help='Monte Carlo trials per combo within each grid cell.',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility.',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=min(16, os.cpu_count() or 1),
        help='Number of worker processes (max 16).',
    )
    args = parser.parse_args()

    random.seed(args.seed)

    if args.events_json is not None:
        if not args.events_json.exists():
            raise FileNotFoundError(f'Events JSON not found at {args.events_json}')
        with args.events_json.open('r', encoding='utf-8') as fh:
            events = json.load(fh)
        if not isinstance(events, list):
            raise ValueError(f'Expected a list of events in {args.events_json}, got {type(events)!r}')
    else:
        if not args.database.exists():
            raise FileNotFoundError(f'Database not found at {args.database}')
        events = load_preflop_shove_events(args.database)
    villain_weights, scenario_stats = build_villain_data(events)

    results = {}
    for scenario_index, (key, (label, _)) in enumerate(SCENARIOS.items()):
        weights = villain_weights[key]
        if not weights:
            continue

        grid, combo_equities = compute_scenario_equity(
            weights,
            args.trials,
            args.workers,
            args.seed + scenario_index * 9973,
        )

        stats = scenario_stats.get(key, {'bet_sum': 0.0, 'pot_sum': 0.0, 'count': 0})
        count = stats['count'] or 1
        avg_bet = stats['bet_sum'] / count if count else 0.0
        avg_bet_added = stats.get('bet_added_sum', 0.0) / count if count else 0.0
        avg_pot_before = stats['pot_sum'] / count if count else 0.0
        assumption = SCENARIO_ASSUMPTIONS.get(key, {'effective_stack_bb': 100.0})
        effective_stack = float(assumption.get('effective_stack_bb', 100.0))
        base_call = avg_bet_added if avg_bet_added > 0 else (avg_bet if avg_bet > 0 else effective_stack)
        call_amount = base_call
        if effective_stack > 0 and call_amount > effective_stack:
            call_amount = effective_stack
        villain_amount = call_amount
        rake_percent = 0.05
        rake_cap_bb = 10.0
        scale_denominator = avg_bet_added if avg_bet_added > 0 else (avg_bet if avg_bet > 0 else None)
        scale_factor = (call_amount / scale_denominator) if scale_denominator else 1.0
        pot_before = avg_pot_before * scale_factor if avg_pot_before > 0 else 1.5
        ev_grid = compute_ev_grid(
            grid,
            call_amount,
            villain_amount,
            pot_before,
            rake_percent=rake_percent,
            rake_cap=rake_cap_bb,
        )

        results[key] = {
            'label': label,
            'grid': grid,
            'equity_grid': grid,
            'ev_grid': ev_grid,
            'combo_equities': combo_equities,
            'call_amount_bb': call_amount,
            'villain_amount_bb': villain_amount,
            'pot_before_bb': pot_before,
            'avg_bet_bb': avg_bet,
            'avg_bet_added_bb': avg_bet_added,
            'avg_pot_before_bb': avg_pot_before,
            'assumed_effective_stack_bb': effective_stack,
            'rake_percent': rake_percent,
            'rake_cap_bb': rake_cap_bb,
            'trials_per_combo': args.trials,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
