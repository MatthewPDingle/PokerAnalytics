#!/usr/bin/env python3
"""Test what happens if we use dealer marker to determine BTN position."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.opponent_performance import POSITIONS_BY_COUNT

def assign_positions_dealer_aware(
    players: list[dict],
    dealt_players: set[str],
    small_blind_name: str | None,
    dealer_name: str | None,
) -> dict[str, str]:
    """Assign positions using dealer as BTN, then rotating from SB."""
    if not players or not dealt_players:
        return {}

    count = len(dealt_players)
    order = POSITIONS_BY_COUNT.get(count)
    if not order or len(order) != count:
        return {}

    # Find SB seat to start rotation
    seat_sorted = sorted([p for p in players if p['name'] in dealt_players], key=lambda p: p['seat'])
    name_to_player = {p['name']: p for p in seat_sorted}

    if small_blind_name and small_blind_name in name_to_player:
        sb_seat = name_to_player[small_blind_name]['seat']
    else:
        # No SB posted - need to infer
        # For now, use first dealt player's seat
        sb_seat = seat_sorted[0]['seat']

    # Start rotation from SB
    seat_numbers = [p['seat'] for p in seat_sorted]
    start_index = next((i for i, p in enumerate(seat_sorted) if p['seat'] == sb_seat), 0)

    rotation: list[dict] = []
    idx = start_index
    visited = 0
    while len(rotation) < count and visited < count * 2:
        player = seat_sorted[idx]
        rotation.append(player)
        idx = (idx + 1) % len(seat_sorted)
        visited += 1

    # Assign positions
    mapping: dict[str, str] = {}
    for position_label, player in zip(order, rotation):
        mapping[player['name']] = position_label

    # Override: if dealer is specified and in dealt players, assign them to BTN
    if dealer_name and dealer_name in dealt_players and 'BTN' in order:
        # First, find who currently has BTN
        current_btn = None
        for name, pos in mapping.items():
            if pos == 'BTN':
                current_btn = name
                break

        # Swap dealer to BTN
        if current_btn and current_btn != dealer_name:
            dealer_old_pos = mapping.get(dealer_name)
            if dealer_old_pos:
                mapping[current_btn] = dealer_old_pos
                mapping[dealer_name] = 'BTN'

    return mapping

def main():
    source = DriveHudDataSource.from_defaults()

    position_counts = defaultdict(int)
    total_hands = 0

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

            # Use dealer-aware positioning
            position_map = assign_positions_dealer_aware(players, dealt_players, sb_name, dealer_name)

            if hero_name in position_map:
                position = position_map[hero_name]
                position_counts[position] += 1
                total_hands += 1

    print("DEALER-AWARE (dealer = BTN) Position Counts:")
    print("="*60)

    expected = {
        'SB': 5821,
        'BB': 5706,
        'LJ': 2067,
        'HJ': 3801,
        'CO': 4778,
        'BTN': 5051,
    }

    for pos in ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BTN']:
        actual = position_counts.get(pos, 0)
        exp = expected.get(pos, 0)
        diff = actual - exp
        status = "✓" if diff == 0 else "✗"
        print(f"{pos:6} Expected: {exp:5}  Actual: {actual:5}  Diff: {diff:+5}  {status}")

    print(f"\nTotal: {total_hands}")

    # Calculate total absolute difference
    total_diff = sum(abs(position_counts.get(pos, 0) - expected.get(pos, 0)) for pos in expected.keys())
    print(f"Total absolute difference: {total_diff}")

if __name__ == "__main__":
    main()
