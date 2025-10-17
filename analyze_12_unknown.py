#!/usr/bin/env python3
"""Analyze the 12 UNKNOWN hands in detail."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

    unknown_cases = []

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

            # Get position
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)
            hero_pos = position_map.get(hero_name, 'UNKNOWN')

            if hero_pos == 'UNKNOWN':
                # This is a dead blind hand where Hero is not assigned
                bb_pos = position_map.get(bb_name, 'UNKNOWN') if bb_name else 'UNKNOWN'

                unknown_cases.append({
                    'hand_id': row.get('HandHistoryId'),
                    'num_players': len(dealt_players),
                    'sb_posted': sb_name,
                    'bb_posted_by': bb_name,
                    'bb_assigned_position': bb_pos,
                    'dealer': dealer_name,
                    'hero_is_dealer': hero_name == dealer_name,
                    'position_map': position_map,
                })

    print(f"Found {len(unknown_cases)} UNKNOWN hands\n")

    for i, case in enumerate(unknown_cases, 1):
        print(f"{i}. Hand {case['hand_id']}: {case['num_players']} players")
        print(f"   SB posted: {case['sb_posted']}")
        print(f"   BB posted by: {case['bb_posted_by']}")
        print(f"   BB assigned position: {case['bb_assigned_position']}")
        print(f"   Dealer: {case['dealer']}")
        print(f"   Hero is dealer: {case['hero_is_dealer']}")
        print(f"   Position map: {case['position_map']}")
        print()

    # Analysis
    print("="*70)
    print("ANALYSIS:")
    print("="*70)
    print(f"All {len(unknown_cases)} cases have:")
    sb_posted_count = sum(1 for c in unknown_cases if c['sb_posted'])
    print(f"  SB posted: {sb_posted_count}")
    print(f"  SB NOT posted (dead blind): {len(unknown_cases) - sb_posted_count}")

    bb_positions = {}
    for case in unknown_cases:
        bb_pos = case['bb_assigned_position']
        bb_positions[bb_pos] = bb_positions.get(bb_pos, 0) + 1

    print(f"\nBB player assigned positions in these hands:")
    for pos, count in sorted(bb_positions.items()):
        print(f"  {pos}: {count}")

    print(f"\nHypothesis: Since Hero is not assigned (dead SB), maybe DriveHUD")
    print(f"assigns Hero to the same position as the BB player?")

if __name__ == "__main__":
    main()
