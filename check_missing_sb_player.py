#!/usr/bin/env python3
"""Check if the player who would be SB is sitting out when no SB is posted."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import POSITIONS_BY_COUNT

def main():
    source = DriveHudDataSource.from_defaults()

    # Get ALL hands
    history_rows = list(source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId ASC'))

    no_sb_cases = []
    sb_player_sitting_out = 0
    sb_player_dealt_in = 0

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
                    is_dealer = player.get('dealer') == '1'
                    if is_dealer:
                        dealer_name = name
                    players.append({
                        'name': name,
                        'seat': int(player.get('seat') or 0),
                        'dealer': is_dealer,
                    })

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

            # Only interested in hands where SB wasn't posted
            if sb_name:
                continue

            if not bb_name:
                continue

            # Figure out who WOULD be SB based on dealer rotation
            seat_sorted = sorted([p for p in players if p['name'] in dealt_players], key=lambda p: p['seat'])

            if dealer_name and dealer_name in dealt_players:
                dealer_idx = next((i for i, p in enumerate(seat_sorted) if p['name'] == dealer_name), None)
                if dealer_idx is not None:
                    count = len(dealt_players)
                    order = POSITIONS_BY_COUNT.get(count)
                    if order:
                        rotation = []
                        for i in range(count):
                            idx = (dealer_idx - (count - 1 - i)) % len(seat_sorted)
                            rotation.append(seat_sorted[idx])

                        # First person in rotation would be SB
                        would_be_sb_player = rotation[0]['name']

                        # Check if there's a player at the table NOT dealt in
                        all_player_names = [p['name'] for p in players]
                        sitting_out = [p for p in all_player_names if p not in dealt_players]

                        # NEW: Check if there's someone who would be between dealer and would_be_sb in full table seating
                        # This would indicate a missing player who should have been SB
                        all_seats_sorted = sorted(players, key=lambda p: p['seat'])

                        # Find dealer in all players
                        dealer_in_all = next((i for i, p in enumerate(all_seats_sorted) if p['name'] == dealer_name), None)
                        if dealer_in_all is not None:
                            # Check the next seat after dealer (wrapping around)
                            next_seat_idx = (dealer_in_all - (count - 1)) % len(all_seats_sorted)
                            expected_sb_from_all_seats = all_seats_sorted[next_seat_idx]['name']

                            case = {
                                'hand_id': row.get('HandHistoryId'),
                                'dealer': dealer_name,
                                'bb_posted_by': bb_name,
                                'would_be_sb_from_dealt': would_be_sb_player,
                                'expected_sb_from_all_seats': expected_sb_from_all_seats,
                                'all_players': all_player_names,
                                'dealt_players': list(dealt_players),
                                'sitting_out': sitting_out,
                                'sb_player_matches': would_be_sb_player == expected_sb_from_all_seats,
                            }

                            no_sb_cases.append(case)

                            if sitting_out:
                                sb_player_sitting_out += 1
                            else:
                                sb_player_dealt_in += 1

    print(f"Total hands where SB wasn't posted: {len(no_sb_cases)}")
    print(f"  Cases where someone is sitting out: {sb_player_sitting_out}")
    print(f"  Cases where everyone is dealt in: {sb_player_dealt_in}")
    print()

    # Show first 10 cases where someone is sitting out
    sitting_out_cases = [c for c in no_sb_cases if c['sitting_out']]
    print(f"First 10 cases where someone is sitting out:")
    print("="*70)
    for i, case in enumerate(sitting_out_cases[:10], 1):
        print(f"\n{i}. Hand {case['hand_id']}:")
        print(f"   Dealer: {case['dealer']}")
        print(f"   BB posted by: {case['bb_posted_by']}")
        print(f"   Would-be SB (from dealt players): {case['would_be_sb_from_dealt']}")
        print(f"   Expected SB (from all seats): {case['expected_sb_from_all_seats']}")
        print(f"   Sitting out: {case['sitting_out']}")
        print(f"   Match? {case['sb_player_matches']}")

    # Show first 10 cases where everyone is dealt in
    all_dealt_cases = [c for c in no_sb_cases if not c['sitting_out']]
    print(f"\n\nFirst 10 cases where everyone is dealt in (but no SB posted):")
    print("="*70)
    for i, case in enumerate(all_dealt_cases[:10], 1):
        print(f"\n{i}. Hand {case['hand_id']}:")
        print(f"   Dealer: {case['dealer']}")
        print(f"   BB posted by: {case['bb_posted_by']}")
        print(f"   Would-be SB: {case['would_be_sb_from_dealt']}")
        print(f"   All players: {case['all_players']}")
        print(f"   Dealt players: {case['dealt_players']}")

if __name__ == "__main__":
    main()
