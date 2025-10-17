#!/usr/bin/env python3
"""Investigate the 12 UNKNOWN position hands."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    _assign_positions_from_actions,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    unknown_hands = []

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

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

            # Get action order
            acting_order = []
            for action in preflop_round.findall('action'):
                name = action.get('player')
                if name and name not in acting_order:
                    acting_order.append(name)

            # Try seat-based positioning first
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

            # Fall back to action-based if seat-based didn't assign hero
            if hero_name not in position_map:
                position_map = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order, dealer_name)

            position = position_map.get(hero_name, 'UNKNOWN')

            if position == 'UNKNOWN':
                unknown_hands.append({
                    'hand_id': row.get('HandHistoryId'),
                    'sb_name': sb_name,
                    'bb_name': bb_name,
                    'dealer_name': dealer_name,
                    'dealt_players': list(dealt_players),
                    'num_players': len(dealt_players),
                    'hero_name': hero_name,
                    'seat_map': position_map,
                })

    print(f"Found {len(unknown_hands)} UNKNOWN position hands")
    print()

    for i, hand in enumerate(unknown_hands, 1):
        print(f"\n{i}. Hand {hand['hand_id']}:")
        print(f"   Players: {hand['num_players']}")
        print(f"   SB: {hand['sb_name']}")
        print(f"   BB: {hand['bb_name']}")
        print(f"   Dealer: {hand['dealer_name']}")
        print(f"   Hero: {hand['hero_name']}")
        print(f"   Dealt players: {hand['dealt_players']}")
        print(f"   Position map: {hand['seat_map']}")

if __name__ == "__main__":
    main()
