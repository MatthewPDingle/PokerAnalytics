#!/usr/bin/env python3
"""Debug Hero as dealer in dead blind hands."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    source = DriveHudDataSource.from_defaults()

    # Get first dead blind hand where Hero is dealer
    row = list(source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories WHERE HandHistoryId = 131'))[0]

    session = ET.fromstring(row['HandHistory'])
    session_general = session.find('general')
    hero_name = session_general.findtext('nickname')

    print(f"Hand 131 - Hero: {hero_name}")
    print()

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

        print(f"Players (sorted by seat):")
        for p in sorted(players, key=lambda x: x['seat']):
            dealer_mark = " (D)" if p['dealer'] else ""
            hero_mark = " [HERO]" if p['name'] == hero_name else ""
            print(f"  Seat {p['seat']}: {p['name']}{dealer_mark}{hero_mark}")

        preflop_round = game.find("round[@no='1']")
        dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

        # Simulate our rotation logic
        seat_sorted = sorted([p for p in players if p['name'] in dealt_players], key=lambda p: p['seat'])
        dealer_idx = next((i for i, p in enumerate(seat_sorted) if p['name'] == dealer_name), None)

        print(f"\nDealer: {dealer_name}, Dealer index in seat_sorted: {dealer_idx}")
        print(f"Seat sorted: {[p['name'] for p in seat_sorted]}")

        count = len(dealt_players)
        rotation = []
        for i in range(count):
            idx = (dealer_idx - (count - 1 - i)) % len(seat_sorted)
            rotation.append(seat_sorted[idx])

        print(f"\nRotation (backwards from dealer):")
        for i, p in enumerate(rotation):
            dealer_mark = " (D)" if p['dealer'] else ""
            hero_mark = " [HERO]" if p['name'] == hero_name else ""
            print(f"  rotation[{i}]: {p['name']}{dealer_mark}{hero_mark}")

        # Check blinds
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
        print(f"  SB posted: {sb_name}")
        print(f"  BB posted: {bb_name}")

        print(f"\nDead blind? {not sb_name and bb_name}")
        print(f"Hero is dealer? {hero_name == dealer_name}")
        print(f"Hero at rotation[0]? {rotation[0]['name'] == hero_name}")
        print(f"Hero at rotation[{count-1}]? {rotation[count-1]['name'] == hero_name}")

if __name__ == "__main__":
    main()
