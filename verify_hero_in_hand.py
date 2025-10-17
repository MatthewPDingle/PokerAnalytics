#!/usr/bin/env python3
"""Verify hero is actually dealt in and not sitting out."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    source = DriveHudDataSource.from_defaults()

    # Check a few specific hands
    test_hand_ids = [123, 587, 707, 1596, 14636]  # Some of the hands we mentioned

    for hand_id in test_hand_ids:
        row = list(source.rows(f'SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories WHERE HandHistoryId = {hand_id}'))

        if not row:
            print(f"Hand {hand_id}: NOT FOUND")
            continue

        row = row[0]
        text = row.get('HandHistory')
        if not text:
            continue

        try:
            session = ET.fromstring(text)
        except ET.ParseError:
            print(f"Hand {hand_id}: PARSE ERROR")
            continue

        session_general = session.find('general')
        hero_name = session_general.findtext('nickname') if session_general is not None else None
        start_date = session_general.findtext('startdate') if session_general is not None else None

        print(f"\n{'='*70}")
        print(f"Hand {hand_id} (HandNumber: {row.get('HandNumber')})")
        print(f"Date: {start_date}")
        print(f"Hero name in session: {hero_name}")
        print(f"{'='*70}")

        for game in session.findall('game'):
            players_section = game.find('./general/players')
            if players_section is None:
                print("  No players section found")
                continue

            print(f"\nAll players at table:")
            all_players = []
            for player in players_section.findall('player'):
                name = player.get('name')
                seat = player.get('seat')
                dealer = player.get('dealer') == '1'
                all_players.append(name)
                dealer_mark = " (D)" if dealer else ""
                hero_mark = " [HERO]" if name == hero_name else ""
                print(f"  Seat {seat}: {name}{dealer_mark}{hero_mark}")

            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                print("\n  No preflop round found")
                continue

            print(f"\nPlayers dealt cards:")
            dealt_players = []
            for cards_elem in preflop_round.findall('cards'):
                if cards_elem.get('type') == 'Pocket':
                    player = cards_elem.get('player')
                    cards = cards_elem.text
                    dealt_players.append(player)
                    hero_mark = " [HERO]" if player == hero_name else ""
                    print(f"  {player}: {cards}{hero_mark}")

            print(f"\nHero is in dealt players list? {hero_name in dealt_players}")

            if hero_name not in dealt_players:
                print(f"  WARNING: Hero ({hero_name}) was NOT dealt cards!")
                print(f"  All players at table: {all_players}")
                print(f"  Dealt players: {dealt_players}")
                print(f"  Sitting out: {[p for p in all_players if p not in dealt_players]}")

            # Check blinds
            round_zero = game.find("round[@no='0']")
            if round_zero is not None:
                print(f"\nBlinds posted:")
                for action in round_zero.findall('action'):
                    action_type = action.get('type')
                    player = action.get('player')
                    amount = action.get('sum')
                    if action_type == '1':
                        print(f"  SB: {player} ({amount})")
                    elif action_type == '2':
                        print(f"  BB: {player} ({amount})")
            else:
                print("\n  No round 0 (blinds) found")

if __name__ == "__main__":
    main()
