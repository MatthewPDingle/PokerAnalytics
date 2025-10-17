#!/usr/bin/env python3
"""Detailed analysis of dead blind position assignments."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)
from collections import Counter

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

    dead_blind_position_counts = Counter()
    total_dead_blind = 0

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

            # Only dead blind hands (no SB posted)
            if sb_name or not bb_name:
                continue

            total_dead_blind += 1

            # Get our position assignment
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

            # Count each position assignment
            for player, pos in position_map.items():
                dead_blind_position_counts[pos] += 1

    print(f"Total dead blind hands: {total_dead_blind}")
    print(f"\nPosition assignments in dead blind hands (all players):")
    for pos in ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BTN', 'UNKNOWN']:
        count = dead_blind_position_counts.get(pos, 0)
        print(f"  {pos}: {count}")

    print(f"\nTotal position assignments in dead blind: {sum(dead_blind_position_counts.values())}")
    print(f"Expected (if all players assigned): {total_dead_blind * 6} (assuming mostly 6-max)")

    # Hypothesis: If we're overcounting SB by 120 and undercounting others,
    # maybe the dead SB player should be getting assigned to their seat position
    # (which would be BB in most cases based on our earlier finding)
    print(f"\nOur current SB overcount: +120")
    print(f"If {total_dead_blind} dead blind hands assign SB incorrectly...")
    print(f"Maybe the person who would-be dead SB should be assigned BB instead?")

if __name__ == "__main__":
    main()
