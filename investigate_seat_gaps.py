#!/usr/bin/env python3
"""Investigate hands with non-consecutive seat numbers (gaps in seating)."""

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

    gap_cases = []

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories LIMIT 10000')

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
            players_section = game.find('./general/players')
            if players_section is None:
                continue

            players = []
            for player in players_section.findall('player'):
                name = player.get('name')
                if name:
                    players.append({
                        'name': name,
                        'seat': int(player.get('seat') or 0),
                        'dealer': player.get('dealer') == '1',
                    })

            # Get dealt players
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

            # Check for seat gaps
            seats = sorted([p['seat'] for p in players])
            max_seat = max(seats)

            # Check if seats are NOT consecutive
            has_gaps = False
            if len(seats) < max_seat:  # If max seat > number of players, there must be gaps
                has_gaps = True

            if has_gaps:
                # Get positions using both methods
                round_zero = game.find("round[@no='0']")
                sb_name = None
                bb_name = None
                if round_zero is not None:
                    for action in round_zero.findall('action'):
                        if action.get('type') == '1':
                            sb_name = action.get('player')
                        if action.get('type') == '2':
                            bb_name = action.get('player')

                acting_order = []
                for action in preflop_round.findall('action'):
                    name = action.get('player')
                    if name and name not in acting_order:
                        acting_order.append(name)

                # Method 1: Action-based
                positions_action = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)

                # Method 2: Seat-based
                positions_seat = _assign_positions_from_seats(players, dealt_players, sb_name)

                # Which one did we use?
                our_positions = positions_action
                if not our_positions or hero_name not in our_positions:
                    our_positions = positions_seat

                hero_pos = our_positions.get(hero_name, 'UNKNOWN')

                gap_cases.append({
                    'hand_id': row.get('HandHistoryId'),
                    'seats': seats,
                    'max_seat': max_seat,
                    'num_players': len(players),
                    'hero_pos_action': positions_action.get(hero_name, 'N/A'),
                    'hero_pos_seat': positions_seat.get(hero_name, 'N/A'),
                    'hero_pos_final': hero_pos,
                    'sb': sb_name,
                    'bb': bb_name,
                })

    print(f"Found {len(gap_cases)} hands with seat gaps (non-consecutive seating)")
    print()

    if len(gap_cases) > 0:
        print("First 10 examples:")
        for i, case in enumerate(gap_cases[:10], 1):
            print(f"\n{i}. Hand {case['hand_id']}:")
            print(f"   Seats occupied: {case['seats']} (max seat: {case['max_seat']})")
            print(f"   {case['num_players']} players")
            print(f"   SB: {case['sb']}, BB: {case['bb']}")
            print(f"   Hero position (action-based): {case['hero_pos_action']}")
            print(f"   Hero position (seat-based): {case['hero_pos_seat']}")
            print(f"   Hero position (final): {case['hero_pos_final']}")

        # Check if action vs seat methods disagree
        disagreements = [c for c in gap_cases if c['hero_pos_action'] != c['hero_pos_seat'] and c['hero_pos_action'] != 'N/A']
        if disagreements:
            print(f"\n\nFound {len(disagreements)} cases where action-based and seat-based methods DISAGREE!")
            for i, case in enumerate(disagreements[:5], 1):
                print(f"\n{i}. Hand {case['hand_id']}:")
                print(f"   Action-based: {case['hero_pos_action']}")
                print(f"   Seat-based: {case['hero_pos_seat']}")

    else:
        print("No hands found with seat gaps - all players are in consecutive seats!")

if __name__ == "__main__":
    main()
