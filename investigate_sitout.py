#!/usr/bin/env python3
"""Investigate hands where players might be sitting out."""

import xml.etree.ElementTree as ET
from collections import Counter
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Track cases where total players != dealt players
    sitout_cases = []
    position_shifts = Counter()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories LIMIT 5000')

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

        if not hero_name:
            continue

        for game in session.findall('game'):
            # Get ALL players at the table
            players_section = game.find('./general/players')
            if players_section is None:
                continue

            all_players = []
            for player in players_section.findall('player'):
                name = player.get('name')
                if name:
                    all_players.append({
                        'name': name,
                        'seat': int(player.get('seat') or 0),
                        'dealer': player.get('dealer') == '1',
                    })

            # Get dealt players (who actually got cards)
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

            total_players = len(all_players)
            dealt_count = len(dealt_players)

            # If someone is sitting out
            if total_players != dealt_count:
                # Get blinds
                round_zero = game.find("round[@no='0']")
                sb_name = None
                bb_name = None
                if round_zero is not None:
                    for action in round_zero.findall('action'):
                        if action.get('type') == '1':
                            sb_name = action.get('player')
                        if action.get('type') == '2':
                            bb_name = action.get('player')

                # Get action order
                acting_order = []
                for action in preflop_round.findall('action'):
                    name = action.get('player')
                    if name and name not in acting_order:
                        acting_order.append(name)

                # Assign positions
                our_positions = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)
                if not our_positions or hero_name not in our_positions:
                    our_positions = _assign_positions_from_seats(all_players, dealt_players, sb_name)

                hero_pos = our_positions.get(hero_name, 'UNKNOWN')

                sitout_cases.append({
                    'hand_id': row.get('HandHistoryId'),
                    'total_players': total_players,
                    'dealt_players': dealt_count,
                    'hero_position': hero_pos,
                    'all_players': [p['name'] for p in all_players],
                    'dealt_only': list(dealt_players),
                    'sitting_out': [p['name'] for p in all_players if p['name'] not in dealt_players],
                })

                position_shifts[f"{total_players}p_table_{dealt_count}p_dealt"] += 1

    print(f"Found {len(sitout_cases)} hands where players were sitting out")
    print()

    if position_shifts:
        print("Distribution of sit-out scenarios:")
        for scenario, count in sorted(position_shifts.items()):
            print(f"  {scenario}: {count} hands")
        print()

    # Show first few examples
    print("First 10 examples of sit-out hands:")
    for i, case in enumerate(sitout_cases[:10], 1):
        print(f"\n{i}. Hand {case['hand_id']}:")
        print(f"   Table: {case['total_players']} players seated")
        print(f"   Dealt: {case['dealt_players']} players in hand")
        print(f"   Hero position: {case['hero_position']}")
        print(f"   Sitting out: {', '.join(case['sitting_out'])}")

    # Calculate impact
    print("\n" + "="*70)
    print("IMPACT ANALYSIS:")
    print("="*70)

    # Count how positions are assigned in sit-out hands
    sitout_position_counts = Counter()
    for case in sitout_cases:
        sitout_position_counts[case['hero_position']] += 1

    print("\nHero positions in sit-out hands:")
    for pos in sorted(sitout_position_counts.keys()):
        print(f"  {pos}: {sitout_position_counts[pos]}")

    print(f"\nTotal sit-out hands: {sum(sitout_position_counts.values())}")
    print(f"As % of total database: {sum(sitout_position_counts.values()) / 27224 * 100:.2f}%")

if __name__ == "__main__":
    main()
