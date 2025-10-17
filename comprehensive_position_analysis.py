#!/usr/bin/env python3
"""Comprehensive analysis of position assignment discrepancies."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import _parse_game

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories ORDER BY HandHistoryId')

    total_hands = 0
    position_distribution = {}
    dead_blind_hands = 0
    dead_blind_with_hero_sb = 0
    dead_blind_with_hero_bb = 0

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
        gametype = session_general.findtext('gametype') if session_general is not None else None

        if not hero_name:
            continue

        for game in session.findall('game'):
            # Check for dead blind first
            round_zero = game.find("round[@no='0']")
            sb_posted = False
            bb_poster = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_posted = True
                    if action.get('type') == '2':
                        bb_poster = action.get('player')

            parsed = _parse_game(game, hero_name, gametype)
            if not parsed:
                continue

            opponents, position, net_cents, net_bb, pot_bb, vpip, pfr, three_bet, opportunity = parsed

            total_hands += 1
            position_distribution[position] = position_distribution.get(position, 0) + 1

            if not sb_posted and bb_poster:
                dead_blind_hands += 1
                if position == 'SB':
                    dead_blind_with_hero_sb += 1
                if position == 'BB':
                    dead_blind_with_hero_bb += 1

    print(f"Total hands processed: {total_hands}")
    print(f"\nPosition distribution:")
    for pos in ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BTN', 'UTG', 'UTG+1', 'UTG+2', 'UNKNOWN']:
        count = position_distribution.get(pos, 0)
        if count > 0:
            print(f"  {pos}: {count}")

    print(f"\nDead blind statistics:")
    print(f"  Total dead blind hands: {dead_blind_hands}")
    print(f"  Hero assigned SB in dead blind: {dead_blind_with_hero_sb}")
    print(f"  Hero assigned BB in dead blind: {dead_blind_with_hero_bb}")

    print(f"\nExpected totals from DriveHUD:")
    print(f"  SB: 5821")
    print(f"  BB: 5706")
    print(f"  LJ: 2067")
    print(f"  HJ: 3801")
    print(f"  CO: 4778")
    print(f"  BTN: 5051")
    print(f"  Total: 27224")

if __name__ == "__main__":
    main()
