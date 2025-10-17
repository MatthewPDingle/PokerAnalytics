#!/usr/bin/env python3
"""Diagnose position assignment issue by examining specific hands."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Check a sample of 6-max hands to see position assignments
    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories LIMIT 100')

    six_max_count = 0
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
            # Get players
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

            # Get dealt players from preflop
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

            # Only look at 6-max hands
            if len(dealt_players) != 6:
                continue

            six_max_count += 1
            if six_max_count > 3:  # Just show first few
                break

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

            # Assign positions using our current method
            our_positions = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)
            if not our_positions or hero_name not in our_positions:
                our_positions = _assign_positions_from_seats(players, dealt_players, sb_name)

            print(f"\n{'='*70}")
            print(f"6-Max Hand #{six_max_count} (HandHistoryId: {row.get('HandHistoryId')})")
            print(f"{'='*70}")
            print(f"\nPlayers ({len(dealt_players)} dealt):")
            for p in sorted(players, key=lambda x: x['seat']):
                dealer_mark = " (BTN)" if p.get('dealer') else ""
                sb_mark = " (SB)" if p['name'] == sb_name else ""
                bb_mark = " (BB)" if p['name'] == bb_name else ""
                hero_mark = " [HERO]" if p['name'] == hero_name else ""
                if p['name'] in dealt_players:
                    print(f"  Seat {p['seat']}: {p['name']}{dealer_mark}{sb_mark}{bb_mark}{hero_mark}")

            print(f"\nPreflop action order: {acting_order}")
            print(f"\nOur position assignments:")
            for player, pos in sorted(our_positions.items(), key=lambda x: POSITIONS_BY_COUNT[6].index(x[1]) if x[1] in POSITIONS_BY_COUNT[6] else 99):
                hero_mark = " [HERO]" if player == hero_name else ""
                print(f"  {pos}: {player}{hero_mark}")

            print(f"\nHero position: {our_positions.get(hero_name, 'UNKNOWN')}")

    print(f"\n\nTotal 6-max hands examined: {six_max_count}")

if __name__ == "__main__":
    main()
