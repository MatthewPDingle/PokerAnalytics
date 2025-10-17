#!/usr/bin/env python3
"""Check 6-max position assignments against DriveHUD."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    _assign_positions_from_actions,
    POSITIONS_BY_COUNT
)
from collections import Counter

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

    position_counts = Counter()
    dealer_present_count = 0
    dealer_absent_count = 0
    fallback_count = 0

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

            # Only 6-player hands
            if len(dealt_players) != 6:
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

            preflop_actions = [
                {'player': action.get('player'), 'type': action.get('type')}
                for action in preflop_round.findall('action')
            ]
            acting_order = []
            for action in preflop_actions:
                name = action.get('player')
                if name and name not in acting_order:
                    acting_order.append(name)

            # Get position using our logic
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)
            used_fallback = False
            if hero_name not in position_map:
                position_map = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order, dealer_name)
                used_fallback = True
                fallback_count += 1

            hero_pos = position_map.get(hero_name, 'UNKNOWN')
            position_counts[hero_pos] += 1

            if dealer_name:
                dealer_present_count += 1
            else:
                dealer_absent_count += 1

    print(f"6-player hands position counts:")
    for pos in ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BTN', 'UNKNOWN']:
        count = position_counts.get(pos, 0)
        print(f"  {pos}: {count}")

    print(f"\nDiagnostics:")
    print(f"  Hands with dealer marked: {dealer_present_count}")
    print(f"  Hands without dealer marked: {dealer_absent_count}")
    print(f"  Times fallback to action-based: {fallback_count}")

    print(f"\nExpected from DriveHUD (for LJ position): 2067")
    print(f"Our count: {position_counts['LJ']}")
    print(f"Difference: {position_counts['LJ'] - 2067}")

if __name__ == "__main__":
    main()
