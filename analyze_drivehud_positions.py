#!/usr/bin/env python3
"""Analyze how DriveHUD actually stores position data in the database."""

import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    """Examine actual position data from DriveHUD database."""

    source = DriveHudDataSource.from_defaults()
    if not source.is_available():
        print(f"Database not available at {source.db_path}")
        return

    print(f"Connected to database: {source.db_path}\n")

    # Sample some hands to see the raw data
    history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId LIMIT 20')

    for idx, row in enumerate(history_rows):
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

        print(f"\n{'='*60}")
        print(f"Hand #{idx + 1} (HandHistoryId: {row.get('HandHistoryId')})")
        print(f"{'='*60}")

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

            # Get blinds
            round_zero = game.find("round[@no='0']")
            small_blind_name = None
            big_blind_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        small_blind_name = action.get('player')
                    if action.get('type') == '2':
                        big_blind_name = action.get('player')

            # Get preflop actions to determine action order
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

            preflop_actions = []
            for action in preflop_round.findall('action'):
                actor = action.get('player')
                if actor:
                    preflop_actions.append(actor)

            # Remove duplicates while preserving order
            action_order = []
            seen = set()
            for actor in preflop_actions:
                if actor not in seen:
                    action_order.append(actor)
                    seen.add(actor)

            print(f"\nTotal Players: {len(players)}")
            print(f"Dealt Players: {len(dealt_players)}")
            print(f"Hero: {hero_name}")
            print(f"SB: {small_blind_name}")
            print(f"BB: {big_blind_name}")
            print(f"\nSeats:")
            for p in sorted(players, key=lambda x: x['seat']):
                dealer_mark = " (D)" if p.get('dealer') else ""
                in_hand = " [dealt]" if p['name'] in dealt_players else ""
                hero_mark = " [HERO]" if p['name'] == hero_name else ""
                print(f"  Seat {p['seat']}: {p['name']}{dealer_mark}{in_hand}{hero_mark}")

            print(f"\nPreflop Action Order: {action_order}")

            # Show what position each player would get
            print(f"\nExpected positions (from action order):")
            if len(dealt_players) == 2:
                positions = ["SB", "BB"]
            elif len(dealt_players) == 3:
                positions = ["SB", "BB", "BTN"]
            elif len(dealt_players) == 4:
                positions = ["SB", "BB", "CO", "BTN"]
            elif len(dealt_players) == 5:
                positions = ["SB", "BB", "HJ", "CO", "BTN"]
            elif len(dealt_players) == 6:
                positions = ["SB", "BB", "LJ", "HJ", "CO", "BTN"]
            else:
                positions = [f"POS_{i}" for i in range(len(dealt_players))]

            # Assign positions
            mapping = {}
            if small_blind_name and small_blind_name in dealt_players:
                mapping[small_blind_name] = positions[0]
            if big_blind_name and big_blind_name in dealt_players and len(positions) > 1:
                mapping[big_blind_name] = positions[1]

            remaining_positions = positions[2:]
            remaining_players = [name for name in action_order if name in dealt_players and name not in mapping]

            for player, pos in zip(remaining_players, remaining_positions):
                mapping[player] = pos

            for player, pos in mapping.items():
                hero_mark = " [HERO]" if player == hero_name else ""
                print(f"  {player}: {pos}{hero_mark}")

            if idx >= 4:  # Just show first 5 hands for debugging
                print("\n... stopping after 5 hands for brevity ...")
                return

if __name__ == "__main__":
    main()
