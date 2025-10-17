#!/usr/bin/env python3
"""Analyze dead blind hands by table size."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)
from collections import Counter, defaultdict

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

    dead_blind_by_size = Counter()
    positions_by_size = defaultdict(Counter)

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

            table_size = len(dealt_players)
            dead_blind_by_size[table_size] += 1

            # Get our position assignment
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

            # Count each position assignment for this table size
            for player, pos in position_map.items():
                positions_by_size[table_size][pos] += 1

    total = sum(dead_blind_by_size.values())
    print(f"Dead blind hands by table size (Total: {total}):")
    for size in sorted(dead_blind_by_size.keys()):
        count = dead_blind_by_size[size]
        print(f"  {size} players: {count} hands")

    print(f"\nPosition assignments in dead blind hands by table size:")
    for size in sorted(positions_by_size.keys()):
        print(f"\n{size} players ({dead_blind_by_size[size]} hands):")
        positions = positions_by_size[size]
        expected_order = POSITIONS_BY_COUNT.get(size, [])
        for pos in expected_order:
            count = positions.get(pos, 0)
            print(f"    {pos}: {count}")

    # Key insight: In dead blind scenarios, there are only N-1 positions being assigned
    # because the dead SB player is getting the BB position (they're posting BB)
    print(f"\n" + "="*70)
    print(f"KEY INSIGHT:")
    print(f"="*70)
    print(f"In dead blind hands, the player who would-be SB is posting BB.")
    print(f"So there's no one in the SB position - it skips directly to BB.")
    print(f"This means in a 6-player dead blind hand:")
    print(f"  - Position 0 (would-be SB) actually posts BB → gets assigned BB")
    print(f"  - Position 1 (would-be BB) gets pushed to next position")
    print(f"  - And so on...")
    print(f"\nMaybe DriveHUD doesn't count dead blind hands at all?")

if __name__ == "__main__":
    main()
