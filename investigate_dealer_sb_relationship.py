#!/usr/bin/env python3
"""Investigate relationship between dealer button and SB when SB isn't posted."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    missing_sb_cases = []

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
            if sb_name:
                continue

            if not bb_name:
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

            # Check if dealer == SB in these cases
            dealer_in_dealt = dealer_name in dealt_players if dealer_name else False

            # Find who we assigned as SB
            our_sb = None
            for player, pos in our_positions.items():
                if pos == 'SB':
                    our_sb = player
                    break

            missing_sb_cases.append({
                'hand_id': row.get('HandHistoryId'),
                'num_players': len(dealt_players),
                'dealer_name': dealer_name,
                'bb_name': bb_name,
                'dealer_in_dealt': dealer_in_dealt,
                'our_sb_assignment': our_sb,
                'dealer_is_our_sb': (dealer_name == our_sb) if dealer_name else False,
                'acting_order': acting_order,
                'dealt_players': list(dealt_players),
                'our_positions': our_positions,
            })

    print(f"Found {len(missing_sb_cases)} hands where SB wasn't posted")
    print()

    if missing_sb_cases:
        dealer_matches = sum(1 for c in missing_sb_cases if c['dealer_is_our_sb'])
        dealer_in_play = sum(1 for c in missing_sb_cases if c['dealer_in_dealt'])

        print(f"Dealer button was in the dealt players: {dealer_in_play}/{len(missing_sb_cases)}")
        print(f"Our SB assignment matches dealer: {dealer_matches}/{len(missing_sb_cases)}")
        print()

        # Show first 10 examples with more detail
        print("First 10 examples:")
        for i, case in enumerate(missing_sb_cases[:10], 1):
            print(f"\n{i}. Hand {case['hand_id']}: {case['num_players']} players")
            print(f"   Dealer: {case['dealer_name']}")
            print(f"   BB: {case['bb_name']}")
            print(f"   Our SB assignment: {case['our_sb_assignment']}")
            print(f"   Dealer is our SB? {case['dealer_is_our_sb']}")
            print(f"   Action order: {case['acting_order']}")
            print(f"   Position assignments:")
            expected_order = POSITIONS_BY_COUNT.get(case['num_players'], [])
            for pos in expected_order:
                player = [p for p, po in case['our_positions'].items() if po == pos]
                player_name = player[0] if player else "UNASSIGNED"
                dealer_mark = " (D)" if player_name == case['dealer_name'] else ""
                bb_mark = " (BB)" if player_name == case['bb_name'] else ""
                print(f"     {pos}: {player_name}{dealer_mark}{bb_mark}")

        # Check if dealer is ALWAYS one position before BB when not SB
        print("\n" + "="*70)
        print("Pattern Analysis:")
        print("="*70)

        # In poker, dealer button is typically at BTN position
        # When SB isn't posted, maybe dealer=BTN and we should assign SB differently

        dealer_at_btn = 0
        for case in missing_sb_cases:
            expected_order = POSITIONS_BY_COUNT.get(case['num_players'], [])
            if 'BTN' in expected_order and case['dealer_name']:
                # Check if dealer is assigned to BTN
                dealer_pos = case['our_positions'].get(case['dealer_name'], 'UNKNOWN')
                if dealer_pos == 'BTN':
                    dealer_at_btn += 1

        print(f"Dealer assigned to BTN position: {dealer_at_btn}/{len(missing_sb_cases)}")

if __name__ == "__main__":
    main()
