#!/usr/bin/env python3
"""Debug script to understand position counting discrepancies."""

from collections import Counter
import xml.etree.ElementTree as ET

from poker_analytics.data.drivehud import DriveHudDataSource

def main():
    """Analyze position assignments in the database."""

    source = DriveHudDataSource.from_defaults()
    if not source.is_available():
        print(f"Database not available at {source.db_path}")
        return

    print(f"Connected to database: {source.db_path}")

    # Get total hand count
    total_hands = source.count("HandHistories")
    print(f"\nTotal hands in database: {total_hands}")

    # Parse all hands and track positions
    position_counts = Counter()
    total_parsed = 0
    failed_parses = 0
    no_hero = 0

    try:
        history_rows = source.rows('SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories ORDER BY HandHistoryId')
    except Exception as e:
        print(f"Error querying database: {e}")
        return

    for row in history_rows:
        text = row.get('HandHistory')
        if not text:
            continue

        try:
            session = ET.fromstring(text)
        except ET.ParseError:
            failed_parses += 1
            continue

        session_general = session.find('general')
        hero_name = session_general.findtext('nickname') if session_general is not None else None
        if not hero_name:
            no_hero += 1
            continue

        # Process each game in the session
        for game in session.findall('game'):
            # Find preflop round to get dealt players
            preflop_round = game.find("round[@no='1']")
            if preflop_round is None:
                continue

            dealt_players = {card.get('player') for card in preflop_round.findall('cards') if card.get('player')}
            if hero_name not in dealt_players:
                continue

            # Get player count
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
                    })

            if not players or len(players) < 2:
                continue

            total_players = len(players)

            # Try to determine hero's position based on player count
            # For now, just count by player count
            total_parsed += 1

            # Try to find SB/BB
            round_zero = game.find("round[@no='0']")
            small_blind_name = None
            big_blind_name = None
            if round_zero is not None:
                for action in round_zero.findall('action'):
                    if action.get('type') == '1' and action.get('player'):
                        small_blind_name = action.get('player')
                    if action.get('type') == '2' and action.get('player'):
                        big_blind_name = action.get('player')

            # Determine position based on total players
            if total_players == 2:
                # Heads up: SB is BTN
                if hero_name == small_blind_name:
                    position_counts['SB'] += 1
                elif hero_name == big_blind_name:
                    position_counts['BB'] += 1
                else:
                    position_counts['UNKNOWN_2P'] += 1
            elif total_players == 3:
                # 3-max: SB, BB, BTN
                if hero_name == small_blind_name:
                    position_counts['SB'] += 1
                elif hero_name == big_blind_name:
                    position_counts['BB'] += 1
                else:
                    position_counts['BTN'] += 1
            elif total_players == 4:
                # 4-max: SB, BB, CO, BTN
                # Need to figure out who is who based on seating
                pass  # Skip for now
            elif total_players == 5:
                # 5-max: SB, BB, HJ, CO, BTN
                pass  # Skip for now
            elif total_players == 6:
                # 6-max: SB, BB, LJ, HJ, CO, BTN
                pass  # Skip for now
            else:
                position_counts[f'PLAYERS_{total_players}'] += 1

    print(f"\nParsing summary:")
    print(f"  Successfully parsed hands: {total_parsed}")
    print(f"  Failed parses: {failed_parses}")
    print(f"  No hero found: {no_hero}")

    print(f"\nPosition counts (simplified):")
    for position, count in sorted(position_counts.items()):
        print(f"  {position}: {count}")

    print(f"\nExpected counts from DriveHUD:")
    print(f"  Total: 27224")
    print(f"  SB: 5821")
    print(f"  BB: 5706")
    print(f"  EP/LJ: 2067")
    print(f"  MP/HJ: 3801")
    print(f"  CO: 4778")
    print(f"  BTN: 5051")

    print(f"\nCurrent app shows:")
    print(f"  SB: 5637")
    print(f"  BB: 5501")
    print(f"  UTG/LJ/EP: 2034")
    print(f"  MP/HJ: 3818")
    print(f"  CO: 4916")
    print(f"  BTN: 5318")

if __name__ == "__main__":
    main()
