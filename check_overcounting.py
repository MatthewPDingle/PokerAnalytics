#!/usr/bin/env python3
"""Check if we're incorrectly assigning dealer to SB when SB was actually posted."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    source = DriveHudDataSource.from_defaults()

    # Count hands with and without SB posts
    sb_posted = 0
    sb_not_posted = 0

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

            if sb_name:
                sb_posted += 1
            elif bb_name:  # BB was posted but SB wasn't
                sb_not_posted += 1

    total = sb_posted + sb_not_posted
    print(f"Total hands: {total}")
    print(f"  SB posted: {sb_posted} ({sb_posted/total*100:.2f}%)")
    print(f"  SB NOT posted (but BB was): {sb_not_posted} ({sb_not_posted/total*100:.2f}%)")

if __name__ == "__main__":
    main()
