#!/usr/bin/env python3
"""Check which hands are returning UNKNOWN with new logic."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

    unknown_count = 0
    unknown_details = []

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
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name, bb_name)
            hero_pos = position_map.get(hero_name, 'UNKNOWN')

            if hero_pos == 'UNKNOWN':
                unknown_count += 1
                if len(unknown_details) < 20:
                    unknown_details.append({
                        'hand_id': row.get('HandHistoryId'),
                        'num_players': len(dealt_players),
                        'sb_posted': sb_name is not None,
                        'bb_posted': bb_name is not None,
                        'has_dealer': dealer_name is not None,
                        'hero_is_dealer': hero_name == dealer_name,
                    })

    print(f"Total UNKNOWN hands: {unknown_count}")
    print(f"\nFirst {len(unknown_details)} UNKNOWN hand details:")
    for i, detail in enumerate(unknown_details, 1):
        print(f"{i}. Hand {detail['hand_id']}: {detail['num_players']} players")
        print(f"   SB posted: {detail['sb_posted']}, BB posted: {detail['bb_posted']}")
        print(f"   Has dealer: {detail['has_dealer']}, Hero is dealer: {detail['hero_is_dealer']}")
        print()

if __name__ == "__main__":
    main()
