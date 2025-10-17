#!/usr/bin/env python3
"""Check which rotation method is used for each hand."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    source = DriveHudDataSource.from_defaults()

    dealer_method_count = 0
    fallback_method_count = 0
    action_method_count = 0

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories')

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

            dealer_name = None
            for player in players_section.findall('player'):
                if player.get('dealer') == '1':
                    dealer_name = player.get('name')
                    break

            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            if hero_name not in dealt_players:
                continue

            # Determine which method would be used
            if dealer_name and dealer_name in dealt_players and len(dealt_players) > 2:
                dealer_method_count += 1
            else:
                fallback_method_count += 1

    total = dealer_method_count + fallback_method_count
    print(f"Total hands: {total}")
    print(f"Dealer-based rotation: {dealer_method_count} ({dealer_method_count/total*100:.2f}%)")
    print(f"Fallback (SB-based) rotation: {fallback_method_count} ({fallback_method_count/total*100:.2f}%)")

if __name__ == "__main__":
    main()
