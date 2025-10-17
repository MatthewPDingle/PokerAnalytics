#!/usr/bin/env python3
"""Find hand with Hero having Kd6c, 6 players, around Oct 10."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Search through October hands
    history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId DESC LIMIT 5000')

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

        # Filter to October
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

            # Get hero's cards
            hero_cards = None
            for cards_elem in preflop_round.findall('cards'):
                if cards_elem.get('type') == 'Pocket' and cards_elem.get('player') == hero_name:
                    hero_cards = cards_elem.text
                    break

            # Check if hero has K and 6 (in any suit combination)
            if hero_cards:
                # Parse cards
                ranks = []
                for part in hero_cards.strip().split():
                    if len(part) == 2:
                        rank = part[1]
                        ranks.append(rank)

                # Check if we have K and 6
                if sorted(ranks) == ['6', 'K']:
                    candidates.append({
                        'hand_id': row.get('HandHistoryId'),
                        'hand_number': row.get('HandNumber'),
                        'start_date': start_date,
                        'hero_cards': hero_cards,
                        'dealer': dealer_name,
                        'num_players': len(dealt_players),
                    })

    print(f"Found {len(candidates)} hands with 6 players where Hero has K-6")
    print()

    for i, hand in enumerate(candidates[:20], 1):
        print(f"{i}. Hand {hand['hand_id']} ({hand['hand_number']})")
        print(f"   Date: {hand['start_date']}")
        print(f"   Hero cards: {hand['hero_cards']}")
        print()

if __name__ == "__main__":
    main()
