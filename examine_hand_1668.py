#!/usr/bin/env python3
"""Examine hand 1668 in detail."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    row = list(source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories WHERE HandHistoryId = 1668'))[0]

    session = ET.fromstring(row['HandHistory'])
    session_general = session.find('general')
    hero_name = session_general.findtext('nickname')
    start_date = session_general.findtext('startdate')

    print(f"{'='*70}")
    print(f"Hand 1668 Analysis")
    print(f"HandNumber: {row.get('HandNumber')}")
    print(f"Date: {start_date}")
    print(f"{'='*70}")

    for game in session.findall('game'):
        players_section = game.find('./general/players')

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
        dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

        # Get pocket cards
        pocket_cards = {}
        for cards_elem in preflop_round.findall('cards'):
            if cards_elem.get('type') == 'Pocket':
                player = cards_elem.get('player')
                cards = cards_elem.text
                if player and cards:
                    pocket_cards[player] = cards

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

        print(f"\nBlinds:")
        print(f"  SB posted by: {sb_name}")
        print(f"  BB posted by: {bb_name}")
        print()

        print(f"Players at table (by seat):")
        for p in sorted(players, key=lambda x: x['seat']):
            dealer_mark = " (D)" if p['name'] == dealer_name else ""
            sb_mark = " (SB)" if p['name'] == sb_name else ""
            bb_mark = " (BB)" if p['name'] == bb_name else ""
            hero_mark = " [HERO]" if p['name'] == hero_name else ""
            cards = pocket_cards.get(p['name'], '??')
            dealt_mark = " *DEALT*" if p['name'] in dealt_players else ""
            print(f"  Seat {p['seat']}: {p['name']}{dealer_mark}{sb_mark}{bb_mark}{hero_mark} - {cards}{dealt_mark}")

        # Get our position assignment
        position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

        print(f"\nOUR position assignments:")
        expected_order = POSITIONS_BY_COUNT.get(len(dealt_players))
        for pos in expected_order:
            player_list = [p for p, po in position_map.items() if po == pos]
            player_name = player_list[0] if player_list else "UNASSIGNED"
            cards = pocket_cards.get(player_name, "??")
            dealer_mark = " (D)" if player_name == dealer_name else ""
            hero_mark = " [HERO]" if player_name == hero_name else ""
            print(f"  {pos}: {player_name} ({cards}){dealer_mark}{hero_mark}")

        print(f"\nOur assignment for Hero: {position_map.get(hero_name, 'UNKNOWN')}")
        print(f"Dealer is: {dealer_name}")
        print(f"Hero is dealer? {hero_name == dealer_name}")
        print(f"\nDead blind hand (no SB posted)? {not sb_name and bb_name}")

if __name__ == "__main__":
    main()
