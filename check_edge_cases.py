#!/usr/bin/env python3
"""Check edge cases: no dealer marked, no SB posted, etc."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    source = DriveHudDataSource.from_defaults()

    no_dealer = 0
    no_sb = 0
    no_dealer_and_no_sb = 0
    total = 0

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

            # Get SB name
            round_zero = game.find("round[@no='0']")
            sb_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_name = action.get('player')
                        break

            total += 1

            if not dealer_name:
                no_dealer += 1
            if not sb_name:
                no_sb += 1
            if not dealer_name and not sb_name:
                no_dealer_and_no_sb += 1

    print(f"Total hands: {total}")
    print(f"No dealer marked: {no_dealer} ({no_dealer/total*100:.2f}%)")
    print(f"No SB posted: {no_sb} ({no_sb/total*100:.2f}%)")
    print(f"No dealer AND no SB: {no_dealer_and_no_sb} ({no_dealer_and_no_sb/total*100:.2f}%)")

if __name__ == "__main__":
    main()
