#!/usr/bin/env python3
"""Analyze where Hero ends up in dead blind scenarios."""

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

    hero_positions_in_dead_blind = Counter()
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

            # Only dead blind hands
            if sb_name or not bb_name:
                continue

            total_dead_blind += 1

            # Get position
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)
            hero_pos = position_map.get(hero_name, 'UNKNOWN')
            hero_positions_in_dead_blind[hero_pos] += 1

    print(f"Total dead blind hands: {total_dead_blind}")
    print(f"\nHero's positions in dead blind hands:")
    for pos in sorted(hero_positions_in_dead_blind.keys()):
        count = hero_positions_in_dead_blind[pos]
        pct = count / total_dead_blind * 100 if total_dead_blind > 0 else 0
        print(f"  {pos}: {count} ({pct:.1f}%)")

    print(f"\n\nIf DriveHUD excludes dead blind hands from position stats:")
    print(f"  We would have {total_dead_blind} fewer hands in our position counts")
    print(f"  Our current BB is +105, dead blind hands are {total_dead_blind}")

if __name__ == "__main__":
    main()
