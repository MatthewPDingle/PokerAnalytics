#!/usr/bin/env python3
"""Find multiple recent hands where no SB was posted."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import POSITIONS_BY_COUNT

def main():
    source = DriveHudDataSource.from_defaults()

    # Get recent hands in reverse order
    history_rows = list(source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId DESC LIMIT 5000'))

    candidates = []

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
        start_date = session_general.findtext('startdate') if session_general is not None else None

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

            # Only interested in hands where SB wasn't posted
            if sb_name:
                continue

            if not bb_name:
                continue

            # Check if hero would be assigned SB using dealer-based rotation
            seat_sorted = sorted([p for p in players if p['name'] in dealt_players], key=lambda p: p['seat'])
            if dealer_name and dealer_name in dealt_players:
                dealer_idx = next((i for i, p in enumerate(seat_sorted) if p['name'] == dealer_name), None)
                if dealer_idx is not None:
                    count = len(dealt_players)
                    order = POSITIONS_BY_COUNT.get(count)
                    if order:
                        rotation = []
                        for i in range(count):
                            idx = (dealer_idx - (count - 1 - i)) % len(seat_sorted)
                            rotation.append(seat_sorted[idx])

                        # Find hero's position in rotation
                        hero_idx = next((i for i, p in enumerate(rotation) if p['name'] == hero_name), None)
                        if hero_idx is not None and hero_idx < len(order):
                            original_position = order[hero_idx]

                            if original_position == 'SB':
                                # Get hero's hole cards
                                hero_cards = None
                                for cards_elem in preflop_round.findall('cards'):
                                    if cards_elem.get('type') == 'Pocket' and cards_elem.get('player') == hero_name:
                                        hero_cards = cards_elem.text
                                        break

                                # Convert card format from "SA H2" to readable format
                                readable_cards = ""
                                if hero_cards:
                                    suit_map = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}
                                    rank_map = {'T': '10', 'J': 'J', 'Q': 'Q', 'K': 'K', 'A': 'A'}
                                    parts = hero_cards.strip().split()
                                    cards_list = []
                                    for part in parts:
                                        if len(part) == 2:
                                            suit_char = part[0]
                                            rank_char = part[1]
                                            suit = suit_map.get(suit_char, suit_char)
                                            rank = rank_map.get(rank_char, rank_char)
                                            cards_list.append(f"{rank}{suit}")
                                    readable_cards = " ".join(cards_list)

                                candidates.append({
                                    'hand_id': row.get('HandHistoryId'),
                                    'hand_number': row.get('HandNumber'),
                                    'start_date': start_date,
                                    'hero_cards': hero_cards,
                                    'readable_cards': readable_cards,
                                    'num_players': len(dealt_players),
                                    'dealer': dealer_name,
                                    'bb': bb_name,
                                    'dealt_players': list(dealt_players),
                                    'all_players': [p['name'] for p in players],
                                })

    if candidates:
        print(f"Found {len(candidates)} hands in the last 5000 where SB wasn't posted and Hero would be SB\n")

        # Show the first 10
        for i, hand in enumerate(candidates[:10], 1):
            print(f"\n{i}. Hand Option:")
            print(f"   Date/Time: {hand['start_date']}")
            print(f"   HandNumber: {hand['hand_number']}")
            print(f"   Your Hole Cards: {hand['readable_cards']}")
            print(f"   Table: {hand['num_players']} players")

            if len(hand['all_players']) > len(hand['dealt_players']):
                sitting_out = [p for p in hand['all_players'] if p not in hand['dealt_players']]
                print(f"   Players sitting out: {sitting_out}")
            else:
                print(f"   All players dealt in")
    else:
        print("No hands found where SB wasn't posted and Hero would be SB")

if __name__ == "__main__":
    main()
