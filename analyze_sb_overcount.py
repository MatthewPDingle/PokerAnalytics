#!/usr/bin/env python3
"""Analyze why SB is overcounted by 120 hands."""

import xml.etree.ElementTree as ET
from collections import Counter
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import (
    _assign_positions_from_seats,
    POSITIONS_BY_COUNT
)

def main():
    source = DriveHudDataSource.from_defaults()

    sb_by_opponent_count = Counter()
    sb_no_blind_posted = []

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

            # Use dealer-aware seat positioning
            position_map = _assign_positions_from_seats(players, dealt_players, sb_name, dealer_name)

            if hero_name in position_map and position_map[hero_name] == 'SB':
                opponent_count = len(dealt_players) - 1
                sb_by_opponent_count[opponent_count] += 1

                # Track cases where SB wasn't posted
                if not sb_name:
                    sb_no_blind_posted.append({
                        'hand_id': row.get('HandHistoryId'),
                        'opponent_count': opponent_count,
                        'dealer': dealer_name,
                    })

    print("SB hands by opponent count (our counts):")
    print("="*60)

    for opp_count in sorted(sb_by_opponent_count.keys()):
        count = sb_by_opponent_count[opp_count]
        print(f"  {opp_count} opponents: {count} hands")

    print(f"\nTotal SB hands (ours): {sum(sb_by_opponent_count.values())}")
    print(f"Expected (DriveHUD): 5821")
    print(f"Difference: +{sum(sb_by_opponent_count.values()) - 5821}")

    print(f"\n\nHero assigned to SB when SB wasn't posted:")
    print(f"  {len(sb_no_blind_posted)} hands")
    print()

    # Show breakdown by opponent count
    no_blind_by_count = Counter()
    for case in sb_no_blind_posted:
        no_blind_by_count[case['opponent_count']] += 1

    print("Breakdown by opponent count:")
    for opp_count in sorted(no_blind_by_count.keys()):
        print(f"  {opp_count} opponents: {no_blind_by_count[opp_count]} hands")

    print(f"\nHypothesis: If DriveHUD doesn't count 'no SB posted' hands as SB,")
    print(f"our count would be: {sum(sb_by_opponent_count.values()) - len(sb_no_blind_posted)}")
    print(f"Expected: 5821")
    print(f"Difference: {sum(sb_by_opponent_count.values()) - len(sb_no_blind_posted) - 5821}")

if __name__ == "__main__":
    main()
