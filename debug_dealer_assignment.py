#!/usr/bin/env python3
"""Debug the dealer-based SB assignment to see what's happening."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_actions,
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    # Track how many times we use dealer for SB
    dealer_sb_count = 0
    normal_sb_count = 0
    seat_based_count = 0

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

            # Get action order
            acting_order = []
            for action in preflop_round.findall('action'):
                name = action.get('player')
                if name and name not in acting_order:
                    acting_order.append(name)

            # Try action-based first
            our_positions = _assign_positions_from_actions(dealt_players, sb_name, bb_name, acting_order, dealer_name)

            if hero_name in our_positions:
                # Check which method was used
                if sb_name:
                    normal_sb_count += 1
                elif dealer_name and dealer_name in dealt_players:
                    # Check if dealer was assigned to SB
                    if our_positions.get(dealer_name) == 'SB':
                        dealer_sb_count += 1
                    else:
                        normal_sb_count += 1
                else:
                    normal_sb_count += 1
            else:
                # Used seat-based method
                our_positions = _assign_positions_from_seats(players, dealt_players, sb_name)
                seat_based_count += 1

    total = dealer_sb_count + normal_sb_count + seat_based_count
    print(f"Total hands processed: {total}")
    print(f"  Normal SB posting: {normal_sb_count} ({normal_sb_count/total*100:.2f}%)")
    print(f"  Dealer-based SB (no SB post): {dealer_sb_count} ({dealer_sb_count/total*100:.2f}%)")
    print(f"  Seat-based fallback: {seat_based_count} ({seat_based_count/total*100:.2f}%)")

if __name__ == "__main__":
    main()
