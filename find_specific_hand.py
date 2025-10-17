#!/usr/bin/env python3
"""Find a specific hand by cards dealt."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
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

    # Looking for:
    # Hero (SB): 3c6s
    # BB: 7hQh
    # EP/LJ: 7dAc
    # MP/HJ: Ah3d
    # CO: 9dKh
    # BTN: 9sKs

    target_cards = {
        'hero': normalize_cards("3c6s"),
        'bb': normalize_cards("7hQh"),
        'ep': normalize_cards("7dAc"),
        'mp': normalize_cards("Ah3d"),
        'co': normalize_cards("9dKh"),
        'btn': normalize_cards("9sKs"),
    }

    print("Searching for hand with these cards:")
    for pos, cards in target_cards.items():
        print(f"  {pos}: {cards}")
    print()

    # Search through recent hands (should be near the end)
    history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId DESC LIMIT 1000')

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

            # Get preflop cards
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            # Extract all pocket cards
            pocket_cards = {}
            for cards_elem in preflop_round.findall('cards'):
                if cards_elem.get('type') == 'Pocket':
                    player = cards_elem.get('player')
                    cards_text = cards_elem.text
                    if player and cards_text:
                        # Convert card format (e.g., "DA HK" to "AhKd")
                        card_parts = cards_text.strip().split()
                        converted = ""
                        for part in card_parts:
                            if len(part) == 2:
                                suit_map = {'D': 'd', 'H': 'h', 'S': 's', 'C': 'c'}
                                rank = part[1]
                                suit = suit_map.get(part[0], part[0].lower())
                                converted += f"{rank}{suit}"
                        pocket_cards[player] = normalize_cards(converted)

            # Check if this matches our target hand
            if len(pocket_cards) != 6:
                continue

            hero_cards = pocket_cards.get(hero_name, "")
            if hero_cards != target_cards['hero']:
                continue

            # Found potential match - check if other cards match
            other_cards = [normalize_cards(c) for p, c in pocket_cards.items() if p != hero_name]
            expected_other = [target_cards['bb'], target_cards['ep'], target_cards['mp'], target_cards['co'], target_cards['btn']]

            if sorted(other_cards) != sorted(expected_other):
                continue

            # FOUND IT!
            print(f"{'='*70}")
            print(f"FOUND THE HAND!")
            print(f"HandHistoryId: {row.get('HandHistoryId')}")
            print(f"HandNumber: {row.get('HandNumber')}")
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

            # Get dealt players
            dealt_players = set(pocket_cards.keys())

            # Get action order
            acting_order = []
            for action in preflop_round.findall('action'):
                name = action.get('player')
                if name and name not in acting_order:
                    acting_order.append(name)

            # Assign positions
            our_positions = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order)
            if not our_positions or hero_name not in our_positions:
                our_positions = _assign_positions_from_seats(players, dealt_players, sb_name)

            print(f"\nPlayers and their cards:")
            for player, cards in pocket_cards.items():
                hero_mark = " [HERO]" if player == hero_name else ""
                print(f"  {player}: {cards}{hero_mark}")

            print(f"\nSB: {sb_name}")
            print(f"BB: {bb_name}")
            print(f"Preflop action order: {acting_order}")

            print(f"\nOUR position assignments:")
            for player, pos in sorted(our_positions.items(), key=lambda x: POSITIONS_BY_COUNT[6].index(x[1]) if x[1] in POSITIONS_BY_COUNT[6] else 99):
                cards = pocket_cards.get(player, "??")
                hero_mark = " [HERO]" if player == hero_name else ""
                print(f"  {pos}: {player} ({cards}){hero_mark}")

            print(f"\nDRIVEHUD expected positions:")
            print(f"  SB: Hero (3c6s) [HERO]")
            print(f"  BB: (7hQh)")
            print(f"  EP/LJ: (7dAc)")
            print(f"  MP/HJ: (Ah3d)")
            print(f"  CO: (9dKh)")
            print(f"  BTN: (9sKs)")

            print(f"\nComparison:")
            our_hero_pos = our_positions.get(hero_name, 'UNKNOWN')
            print(f"  DriveHUD says Hero is: SB")
            print(f"  Our code says Hero is: {our_hero_pos}")
            print(f"  MATCH: {'✓' if our_hero_pos == 'SB' else '✗'}")

            return

    print("Hand not found in recent 1000 hands!")

if __name__ == "__main__":
    main()
