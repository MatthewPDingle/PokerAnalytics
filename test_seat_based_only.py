#!/usr/bin/env python3
"""Test what happens if we ONLY use seat-based positioning (like DriveHUD might do)."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    position_counts = defaultdict(int)
    total_hands = 0

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
            for player in players_section.findall('player'):
                name = player.get('name')
                if name:
                    players.append({
                        'name': name,
                        'seat': int(player.get('seat') or 0),
                        'dealer': player.get('dealer') == '1',
                    })

            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

            # Get SB name
            round_zero = game.find("round[@no='0']")
            sb_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_name = action.get('player')
                        break

            # Use ONLY seat-based positioning
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name)

            if hero_name in position_map:
                position = position_map[hero_name]
                position_counts[position] += 1
                total_hands += 1

    print("SEAT-BASED ONLY Position Counts:")
    print("="*60)

    expected = {
        'SB': 5821,
        'BB': 5706,
        'LJ': 2067,
        'HJ': 3801,
        'CO': 4778,
        'BTN': 5051,
    }

    for pos in ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BTN']:
        actual = position_counts.get(pos, 0)
        exp = expected.get(pos, 0)
        diff = actual - exp
        status = "✓" if diff == 0 else "✗"
        print(f"{pos:6} Expected: {exp:5}  Actual: {actual:5}  Diff: {diff:+5}  {status}")

    print(f"\nTotal: {total_hands}")

if __name__ == "__main__":
    main()
