#!/usr/bin/env python3
"""Check the 25 cases where dealer != our SB assignment when SB not posted."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    mismatches = []

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
            players_section = game.find('./general/players')
            if players_section is None:
                continue

            players = []
            dealer_name = None
            for player in players_section.findall('player'):
                name = player.get('name')
                if name:
                    players.append({
                        'name': name,
                        'seat': int(player.get('seat') or 0),
                        'dealer': player.get('dealer') == '1',
                    })
                    if player.get('dealer') == '1':
                        dealer_name = name

            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

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

            # Only interested in cases where SB wasn't posted
            if sb_name or not bb_name:
                continue

            # Get action order
            acting_order = []
            for action in preflop_round.findall('action'):
                name = action.get('player')
                if name and name not in acting_order:
                    acting_order.append(name)

            # Get our current position assignment
            our_positions = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)
            if not our_positions or hero_name not in our_positions:
                our_positions = _assign_positions_from_seats(players, dealt_players, sb_name)

            # Find who we assigned as SB
            our_sb = None
            for player, pos in our_positions.items():
                if pos == 'SB':
                    our_sb = player
                    break

            # Only track mismatches
            if dealer_name and dealer_name in dealt_players and dealer_name != our_sb:
                mismatches.append({
                    'hand_id': row.get('HandHistoryId'),
                    'num_players': len(dealt_players),
                    'dealer_name': dealer_name,
                    'bb_name': bb_name,
                    'our_sb_assignment': our_sb,
                    'acting_order': acting_order,
                    'dealt_players': sorted(dealt_players),
                    'our_positions': our_positions,
                    'seats': sorted([(p['name'], p['seat']) for p in players], key=lambda x: x[1]),
                })

    print(f"Found {len(mismatches)} hands where dealer != our SB assignment")
    print()

    # Analyze these cases
    for i, case in enumerate(mismatches[:15], 1):
        print(f"\n{i}. Hand {case['hand_id']}: {case['num_players']} players")
        print(f"   Dealer: {case['dealer_name']}")
        print(f"   BB: {case['bb_name']}")
        print(f"   Our SB assignment: {case['our_sb_assignment']}")
        print(f"   Action order: {case['acting_order']}")

        # Show seat layout
        print(f"   Seat layout:")
        for player, seat in case['seats']:
            dealer_mark = " (D)" if player == case['dealer_name'] else ""
            bb_mark = " (BB)" if player == case['bb_name'] else ""
            sb_mark = " (our SB)" if player == case['our_sb_assignment'] else ""
            dealt_mark = " [dealt]" if player in case['dealt_players'] else " [NOT dealt]"
            print(f"     Seat {seat}: {player}{dealer_mark}{bb_mark}{sb_mark}{dealt_mark}")

        # Show positions
        print(f"   Our position assignments:")
        expected_order = POSITIONS_BY_COUNT.get(case['num_players'], [])
        for pos in expected_order:
            player = [p for p, po in case['our_positions'].items() if po == pos]
            player_name = player[0] if player else "UNASSIGNED"
            dealer_mark = " (D)" if player_name == case['dealer_name'] else ""
            bb_mark = " (BB)" if player_name == case['bb_name'] else ""
            print(f"     {pos}: {player_name}{dealer_mark}{bb_mark}")

        # What position did we assign to dealer?
        dealer_pos = case['our_positions'].get(case['dealer_name'], 'UNASSIGNED')
        print(f"   → We assigned dealer to: {dealer_pos}")

    # Check: in these mismatch cases, is dealer not in dealt players?
    dealer_not_dealt = sum(1 for c in mismatches if c['dealer_name'] not in c['dealt_players'])
    print(f"\n\nDealer was sitting out (not dealt): {dealer_not_dealt}/{len(mismatches)}")

if __name__ == "__main__":
    main()
