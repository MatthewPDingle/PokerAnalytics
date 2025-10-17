#!/usr/bin/env python3
"""Find the specific hand: Hero with Kd6c from BTN, 6 players."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def normalize_cards(cards_str):
    """Normalize card string for comparison."""
    if not cards_str:
        return ""
    # Convert to uppercase and remove spaces
    cards = cards_str.upper().replace(" ", "")
    # Parse cards
    parsed = []
    for i in range(0, len(cards), 2):
        if i+1 < len(cards):
            rank = cards[i]
            suit = cards[i+1]
            parsed.append((rank, suit))
    # Sort to normalize order
    parsed.sort()
    return ''.join(f"{r}{s}" for r, s in parsed)

def main():
    source = DriveHudDataSource.from_defaults()

    # Target cards (normalized)
    target_cards = {
        'hero': normalize_cards("Kd6c"),
        'sb': normalize_cards("10c7h"),
        'bb': normalize_cards("Qs5s"),
        'utg': normalize_cards("Ah2s"),
        'mp': normalize_cards("TdTh"),
        'co': normalize_cards("Jd3s"),
    }

    print("Searching for hand with these cards:")
    for pos, cards in target_cards.items():
        print(f"  {pos}: {cards}")
    print()

    # Search through hands around Oct 10 (+/- a few days)
    history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId DESC')

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

        # Filter to around Oct 10
        if start_date and not start_date.startswith('2025-10-'):
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

            # Must be 6 players
            if len(dealt_players) != 6:
                continue

            # Extract all pocket cards
            pocket_cards = {}
            for cards_elem in preflop_round.findall('cards'):
                if cards_elem.get('type') == 'Pocket':
                    player = cards_elem.get('player')
                    cards_text = cards_elem.text
                    if player and cards_text:
                        # Convert card format (e.g., "DK C6" to "6cKd")
                        card_parts = cards_text.strip().split()
                        converted = ""
                        for part in card_parts:
                            if len(part) == 2:
                                suit_map = {'D': 'd', 'H': 'h', 'S': 's', 'C': 'c'}
                                rank_map = {'T': '10', 'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J'}
                                rank = rank_map.get(part[1], part[1])
                                suit = suit_map.get(part[0], part[0].lower())
                                converted += f"{rank}{suit}"
                        pocket_cards[player] = normalize_cards(converted)

            # Check if hero has Kd6c
            hero_cards = pocket_cards.get(hero_name, "")
            if hero_cards != target_cards['hero']:
                continue

            # Check if other cards match
            other_cards = [normalize_cards(c) for p, c in pocket_cards.items() if p != hero_name]
            expected_other = [target_cards['sb'], target_cards['bb'], target_cards['utg'], target_cards['mp'], target_cards['co']]

            if sorted(other_cards) != sorted(expected_other):
                continue

            # FOUND IT!
            print(f"{'='*70}")
            print(f"FOUND THE HAND!")
            print(f"HandHistoryId: {row.get('HandHistoryId')}")
            print(f"HandNumber: {row.get('HandNumber')}")
            print(f"Date: {start_date}")
            print(f"{'='*70}")

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

            # Show all players and their cards
            print(f"\nPlayers and cards:")
            for player, cards in sorted(pocket_cards.items(), key=lambda x: x[0]):
                hero_mark = " [HERO]" if player == hero_name else ""
                dealer_mark = " (D)" if player == dealer_name else ""
                sb_mark = " (SB)" if player == sb_name else ""
                bb_mark = " (BB)" if player == bb_name else ""
                print(f"  {player}: {cards}{hero_mark}{dealer_mark}{sb_mark}{bb_mark}")

            # Get our position assignment
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

            print(f"\nOUR position assignments:")
            expected_order = POSITIONS_BY_COUNT.get(6)
            for pos in expected_order:
                player = [p for p, po in position_map.items() if po == pos]
                player_name = player[0] if player else "UNASSIGNED"
                cards = pocket_cards.get(player_name, "??")
                dealer_mark = " (D)" if player_name == dealer_name else ""
                print(f"  {pos}: {player_name} ({cards}){dealer_mark}")

            print(f"\nDRIVEHUD expected positions:")
            print(f"  SB: (10c7h)")
            print(f"  BB: (Qs5s)")
            print(f"  LJ/UTG/EP: (Ah2s)")
            print(f"  HJ/MP: (10d10h)")
            print(f"  CO: (Jd3s)")
            print(f"  BTN: Hero (Kd6c) [HERO]")

            print(f"\nComparison:")
            our_hero_pos = position_map.get(hero_name, 'UNKNOWN')
            print(f"  DriveHUD says Hero is: BTN")
            print(f"  Our code says Hero is: {our_hero_pos}")
            print(f"  MATCH: {'✓' if our_hero_pos == 'BTN' else '✗'}")

            # Find who we assigned to each position and compare
            print(f"\nDetailed comparison:")
            expected_mapping = {
                'SB': normalize_cards("10c7h"),
                'BB': normalize_cards("Qs5s"),
                'LJ': normalize_cards("Ah2s"),
                'HJ': normalize_cards("10d10h"),
                'CO': normalize_cards("Jd3s"),
                'BTN': normalize_cards("Kd6c"),
            }
            for pos, expected_cards in expected_mapping.items():
                our_player = [p for p, po in position_map.items() if po == pos]
                our_player_name = our_player[0] if our_player else "UNASSIGNED"
                our_cards = pocket_cards.get(our_player_name, "??")
                match = "✓" if our_cards == expected_cards else "✗"
                print(f"  {pos}: Expected {expected_cards}, We have {our_cards} {match}")

            return

    print("Hand not found!")

if __name__ == "__main__":
    main()
