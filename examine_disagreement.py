#!/usr/bin/env python3
"""Examine a specific hand where action vs seat methods disagree."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Get hand #13
    row = list(source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories WHERE HandHistoryId = 13'))[0]

    session = ET.fromstring(row['HandHistory'])
    session_general = session.find('general')
    hero_name = session_general.findtext('nickname')

    for game in session.findall('game'):
        players_section = game.find('./general/players')
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
        dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

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

        print("="*70)
        print(f"Hand #13 Analysis")
        print("="*70)
        print(f"\nPlayers at table:")
        for p in sorted(players, key=lambda x: x['seat']):
            dealer_mark = " (D)" if p.get('dealer') else ""
            sb_mark = " (SB)" if p['name'] == sb_name else ""
            bb_mark = " (BB)" if p['name'] == bb_name else ""
            hero_mark = " [HERO]" if p['name'] == hero_name else ""
            print(f"  Seat {p['seat']}: {p['name']}{dealer_mark}{sb_mark}{bb_mark}{hero_mark}")

        print(f"\nDealt players: {dealt_players}")
        print(f"Preflop action order: {acting_order}")
        print(f"\nNumber of dealt players: {len(dealt_players)}")
        print(f"Expected positions: {POSITIONS_BY_COUNT.get(len(dealt_players))}")

        # Action-based positions
        positions_action = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)
        print(f"\nACTION-BASED positions:")
        for player, pos in sorted(positions_action.items(), key=lambda x: POSITIONS_BY_COUNT[len(dealt_players)].index(x[1]) if x[1] in POSITIONS_BY_COUNT[len(dealt_players)] else 99):
            hero_mark = " [HERO]" if player == hero_name else ""
            print(f"  {pos}: {player}{hero_mark}")

        # Seat-based positions
        positions_seat = _assign_positions_from_seats(players, dealt_players, sb_name)
        print(f"\nSEAT-BASED positions:")
        for player, pos in sorted(positions_seat.items(), key=lambda x: POSITIONS_BY_COUNT[len(dealt_players)].index(x[1]) if x[1] in POSITIONS_BY_COUNT[len(dealt_players)] else 99):
            hero_mark = " [HERO]" if player == hero_name else ""
            print(f"  {pos}: {player}{hero_mark}")

        print(f"\nDISAGREEMENT:")
        print(f"  Action-based says Hero is: {positions_action.get(hero_name, 'NOT ASSIGNED')}")
        print(f"  Seat-based says Hero is: {positions_seat.get(hero_name, 'NOT ASSIGNED')}")

        # Which one are we using?
        our_positions = positions_action
        if not our_positions or hero_name not in our_positions:
            print(f"\n  → Using SEAT-BASED because action-based incomplete")
            our_positions = positions_seat
        else:
            print(f"\n  → Using ACTION-BASED")

        print(f"\n  FINAL: Hero is {our_positions.get(hero_name)}")

if __name__ == "__main__":
    main()
