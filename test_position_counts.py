#!/usr/bin/env python3
"""Test script to verify position counts match DriveHUD."""

from collections import Counter
from poker_analytics.services.opponent_performance import get_opponent_count_performance

def main():
    """Test position counting against DriveHUD expected values."""

    # Expected values from DriveHUD
    expected = {
        "SB": 5821,
        "BB": 5706,
        "LJ": 2067,  # DriveHUD calls this "EP"
        "HJ": 3801,  # DriveHUD calls this "MP"
        "CO": 4778,
        "BTN": 5051,
    }

    print("Fetching opponent count performance data...")
    result = get_opponent_count_performance()

    if not result or 'buckets' not in result:
        print("ERROR: No data returned from get_opponent_count_performance()")
        return

    # Aggregate position counts across all opponent counts
    position_counts = Counter()
    total_hands = 0

    for bucket in result['buckets']:
        opponent_count = bucket['opponent_count']
        positions = bucket.get('positions', [])

        print(f"\n{opponent_count} opponents:")
        for pos_data in positions:
            position = pos_data['position']
            hand_count = pos_data['metrics']['hand_count']
            position_counts[position] += hand_count
            total_hands += hand_count
            print(f"  {position}: {hand_count} hands")

    print("\n" + "="*60)
    print("AGGREGATED POSITION COUNTS:")
    print("="*60)

    # Print comparison
    print(f"\n{'Position':<10} {'Expected':<12} {'Actual':<12} {'Difference':<12} {'Status'}")
    print("-" * 60)

    all_positions = sorted(set(list(expected.keys()) + list(position_counts.keys())))

    total_expected = sum(expected.values())
    total_actual = total_hands
    all_match = True

    for pos in all_positions:
        exp = expected.get(pos, 0)
        act = position_counts.get(pos, 0)
        diff = act - exp
        status = "✓" if diff == 0 else "✗"

        if diff != 0:
            all_match = False

        print(f"{pos:<10} {exp:<12} {act:<12} {diff:+12} {status}")

    print("-" * 60)
    print(f"{'TOTAL':<10} {total_expected:<12} {total_actual:<12} {total_actual - total_expected:+12}")

    print("\n" + "="*60)
    if all_match and total_actual == total_expected:
        print("SUCCESS: All position counts match DriveHUD! ✓")
    else:
        print("FAILURE: Position counts do NOT match DriveHUD ✗")
        print("\nDebugging info:")
        print(f"- Total hands expected: {total_expected}")
        print(f"- Total hands actual: {total_actual}")
        print(f"- Difference: {total_actual - total_expected:+d}")

        # Show any unexpected positions
        unexpected = set(position_counts.keys()) - set(expected.keys())
        if unexpected:
            print(f"\nUnexpected positions found: {unexpected}")
            for pos in unexpected:
                print(f"  {pos}: {position_counts[pos]} hands")

    print("="*60)

if __name__ == "__main__":
    main()
