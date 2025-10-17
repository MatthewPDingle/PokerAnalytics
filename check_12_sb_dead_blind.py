#!/usr/bin/env python3
"""Check the 12 hands where Hero is assigned SB in dead blind."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import _parse_game

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories ORDER BY HandHistoryId')

    sb_dead_blind_hands = []

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
            # Check for dead blind
            round_zero = game.find("round[@no='0']")
            sb_posted = False
            bb_poster = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1':
                        sb_posted = True
                    if action.get('type') == '2':
                        bb_poster = action.get('player')

            if sb_posted or not bb_poster:
                continue  # Not a dead blind hand

            parsed = _parse_game(game, hero_name, gametype)
            if not parsed:
                continue

            opponents, position, net_cents, net_bb, pot_bb, vpip, pfr, three_bet, opportunity = parsed

            if position == 'SB':
                preflop_round = game.find("round[@no='1']")
                dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}

                sb_dead_blind_hands.append({
                    'hand_id': row.get('HandHistoryId'),
                    'table_size': len(dealt_players),
                    'bb_poster': bb_poster,
                    'hero_is_bb_poster': hero_name == bb_poster,
                })

    print(f"Found {len(sb_dead_blind_hands)} hands where Hero is SB in dead blind:\n")

    for i, hand in enumerate(sb_dead_blind_hands, 1):
        print(f"{i}. Hand {hand['hand_id']}: {hand['table_size']} players")
        print(f"   BB poster: {hand['bb_poster']}")
        print(f"   Hero is BB poster: {hand['hero_is_bb_poster']}")
        print()

    print("These are the hands where:")
    print("- No SB was posted (dead blind)")
    print("- Hero was assigned SB position by our rotation logic")
    print("- But Hero is NOT the BB poster")
    print("- So they didn't get reassigned to BB")

if __name__ == "__main__":
    main()
