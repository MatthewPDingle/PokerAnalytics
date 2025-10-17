#!/usr/bin/env python3
"""Investigate why BTN is overcounted by 206 hands."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Track BTN assignments by player count
    btn_by_count = {}

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

            # Get SB name
            round_zero = game.find("round[@no='0']")
            sb_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_name = action.get('player')
                        break

            # Use seat-based positioning
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name)

            if hero_name in position_map and position_map[hero_name] == 'BTN':
                opponent_count = len(dealt_players) - 1
                if opponent_count not in btn_by_count:
                    btn_by_count[opponent_count] = 0
                btn_by_count[opponent_count] += 1

    print("BTN hands by opponent count:")
    print("="*60)

    # DriveHUD's expected BTN counts (from the overall data)
    # We need to back-calculate from the total BTN count
    # Total BTN expected: 5051
    # But we don't have per-opponent-count breakdown from DriveHUD

    # Let's just show our counts
    total_btn = 0
    for opp_count in sorted(btn_by_count.keys()):
        count = btn_by_count[opp_count]
        total_btn += count
        print(f"  {opp_count} opponents: {count} hands")

    print(f"\nTotal BTN hands: {total_btn}")
    print(f"Expected (DriveHUD): 5051")
    print(f"Difference: {total_btn - 5051}")

    # Check if dealer matches our BTN assignment
    print("\n" + "="*60)
    print("Checking if dealer matches BTN in seat-based method...")
    print("="*60)

    dealer_matches_btn = 0
    dealer_not_matches_btn = 0
    no_dealer = 0

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories LIMIT 1000')

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

            # Get SB name
            round_zero = game.find("round[@no='0']")
            sb_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_name = action.get('player')
                        break

            # Use seat-based positioning
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name)

            # Find who got assigned BTN
            btn_player = None
            for player, pos in position_map.items():
                if pos == 'BTN':
                    btn_player = player
                    break

            if not dealer_name:
                no_dealer += 1
            elif dealer_name == btn_player:
                dealer_matches_btn += 1
            else:
                dealer_not_matches_btn += 1

    total_checked = dealer_matches_btn + dealer_not_matches_btn + no_dealer
    print(f"Checked {total_checked} hands:")
    print(f"  Dealer matches our BTN assignment: {dealer_matches_btn} ({dealer_matches_btn/total_checked*100:.2f}%)")
    print(f"  Dealer does NOT match our BTN: {dealer_not_matches_btn} ({dealer_not_matches_btn/total_checked*100:.2f}%)")
    print(f"  No dealer marked: {no_dealer} ({no_dealer/total_checked*100:.2f}%)")

if __name__ == "__main__":
    main()
