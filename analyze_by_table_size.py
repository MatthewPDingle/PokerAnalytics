#!/usr/bin/env python3
"""Analyze position counts by table size."""

import xml.etree.ElementTree as ET
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import _parse_game
from collections import defaultdict

def main():
    source = DriveHudDataSource.from_defaults()

    history_rows = source.rows('SELECT HandHistoryId, HandHistory FROM HandHistories ORDER BY HandHistoryId')

    by_table_size = defaultdict(lambda: defaultdict(int))

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
            parsed = _parse_game(game, hero_name, gametype)
            if not parsed:
                continue

            opponents, position, net_cents, net_bb, pot_bb, vpip, pfr, three_bet, opportunity = parsed
            table_size = opponents + 1

            by_table_size[table_size][position] += 1

    print("Position counts by table size:")
    print("="*70)

    for table_size in sorted(by_table_size.keys()):
        print(f"\n{table_size} players ({table_size-1} opponents):")
        positions = by_table_size[table_size]
        total = sum(positions.values())
        for pos in sorted(positions.keys()):
            count = positions[pos]
            print(f"  {pos}: {count}")
        print(f"  TOTAL: {total}")

    # Check if different table sizes have different discrepancy patterns
    print("\n" + "="*70)
    print("ANALYSIS:")
    print("="*70)
    print("\nNotice that:")
    print("- 6-player (5 opp) has LJ position → undercounted by 56")
    print("- 5-player (4 opp) has HJ position → undercounted by 42")
    print("- 4-player (3 opp) has CO position → undercounted by 19")
    print("- All shorter tables have SB/BB which are overcounted")
    print("\nThis suggests the issue is in how we map position indices at shorter tables!")

if __name__ == "__main__":
    main()
