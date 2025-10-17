from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:  # Optional dependency for DataFrame helpers
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

SUITS = {"S", "H", "D", "C"}
CARD_RANKS = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
BET_TYPES = {"5", "7"}
RAISE_TYPES = {"23", "7"}
CALL_TYPES = {"3"}
FOLD_TYPES = {"0", "4"}
VOLUNTARY_TYPES = {"3", "23", "7", "5"}

BASE_PRIMARY_CATEGORIES: List[str] = [
    "Air",
    "Underpair",
    "Bottom Pair",
    "Middle Pair",
    "Top Pair",
    "Overpair",
    "Two Pair",
    "Trips/Set",
    "Straight",
    "Flush",
    "Full House",
    "Quads",
]

DEFAULT_DRAW_FLAGS: Dict[str, str] = {
    "Flush Draw": "has_flush_draw",
    "OESD": "has_oesd",
    "Made Flush": "made_flush",
    "Made Straight": "made_straight",
}

_BB_REGEX = re.compile(r"\$?([0-9]*\.?[0-9]+)/\$?([0-9]*\.?[0-9]+)")


def _parse_cards(text: str | None) -> List[Tuple[str, int, str]]:
    if not text:
        return []
    parts = [p.strip() for p in text.split() if p.strip()]
    cards: List[Tuple[str, int, str]] = []
    for part in parts:
        if len(part) != 2:
            return []
        suit, rank = part[0], part[1]
        if suit not in SUITS or rank not in CARD_RANKS:
            return []
        cards.append((suit, CARD_RANKS[rank], part))
    return cards


def _extract_big_blind(root: ET.Element) -> float | None:
    for xpath in ("./general/gametype", ".//game/general/gametype"):
        node = root.find(xpath)
        if node is not None and node.text:
            match = _BB_REGEX.search(node.text)
            if match:
                try:
                    return float(match.group(2))
                except ValueError:
                    pass
    for xpath in ("./general/bigblind", ".//game/general/bigblind"):
        node = root.find(xpath)
        if node is not None and node.text:
            try:
                return float(node.text)
            except ValueError:
                pass
    return None


def _has_flush(cards: Iterable[Tuple[str, int, str]]) -> bool:
    counts = Counter(suit for suit, _, _ in cards)
    return any(v >= 5 for v in counts.values())


def _has_flush_draw(hole: List[Tuple[str, int, str]], board: List[Tuple[str, int, str]]) -> bool:
    total = Counter()
    hole_suits = Counter(s for s, _, _ in hole)
    for s, _, _ in hole:
        total[s] += 1
    for s, _, _ in board:
        total[s] += 1
    return any(count >= 4 and hole_suits.get(suit, 0) > 0 for suit, count in total.items())


def _straight_info(hole: List[Tuple[str, int, str]], board: List[Tuple[str, int, str]]) -> Tuple[bool, bool]:
    ranks = [r for _, r, _ in hole + board]
    unique = set(ranks)
    if 14 in unique:
        unique.add(1)
    straight = any(all((start + offset) in unique for offset in range(5)) for start in range(1, 11))
    if straight:
        return True, False
    hole_ranks = set(r for _, r, _ in hole)
    if 14 in hole_ranks:
        hole_ranks.add(1)
    for start in range(1, 12):
        window = {start, start + 1, start + 2, start + 3}
        if window <= unique and window & hole_ranks:
            low = start - 1
            high = start + 4
            if low >= 1 and high <= 14:
                return False, True
    return False, False


def _classify_hand(hole: List[Tuple[str, int, str]], board: List[Tuple[str, int, str]]) -> Dict[str, bool | str]:
    combined = hole + board
    rank_counts = Counter(r for _, r, _ in combined)
    board_ranks = [r for _, r, _ in board]
    board_unique = sorted(set(board_ranks), reverse=True)
    hole_ranks = [r for _, r, _ in hole]
    hole_pair = len(hole_ranks) == 2 and hole_ranks[0] == hole_ranks[1]

    made_flush = _has_flush(combined)
    straight, oesd = _straight_info(hole, board)
    flush_draw = False if made_flush else _has_flush_draw(hole, board)

    counts_sorted = sorted(rank_counts.values(), reverse=True)
    made_four = any(v >= 4 for v in rank_counts.values())
    made_full = len(counts_sorted) >= 2 and counts_sorted[0] >= 3 and counts_sorted[1] >= 2
    made_trips_only = any(v >= 3 for v in rank_counts.values()) and not made_full and not made_four
    made_two_pair = sum(1 for v in rank_counts.values() if v >= 2) >= 2 and not made_full and not made_four

    max_board = board_unique[0] if board_unique else None
    second_board = board_unique[1] if len(board_unique) > 1 else None
    third_board = board_unique[2] if len(board_unique) > 2 else None

    overpair = False
    if hole_pair and max_board is not None and hole_ranks[0] > max_board and not made_two_pair and not made_full and not made_four:
        overpair = True

    top_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair):
        if max_board is not None and any(r == max_board for r in hole_ranks):
            top_pair = True

    middle_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair or top_pair):
        if second_board is not None and any(r == second_board for r in hole_ranks):
            middle_pair = True

    bottom_pair = False
    if not (made_full or made_four or made_trips_only or made_two_pair or overpair or top_pair or middle_pair):
        if third_board is not None and any(r == third_board for r in hole_ranks):
            bottom_pair = True

    underpair = False
    if hole_pair and max_board is not None and hole_ranks[0] < max_board and not made_full and not made_four and not made_trips_only:
        underpair = True

    if made_full:
        primary = "Full House"
    elif made_four:
        primary = "Quads"
    elif made_flush:
        primary = "Flush"
    elif straight:
        primary = "Straight"
    elif made_trips_only:
        primary = "Trips/Set"
    elif made_two_pair:
        primary = "Two Pair"
    elif overpair:
        primary = "Overpair"
    elif top_pair:
        primary = "Top Pair"
    elif middle_pair:
        primary = "Middle Pair"
    elif bottom_pair:
        primary = "Bottom Pair"
    elif underpair:
        primary = "Underpair"
    else:
        primary = "Air"

    return {
        "primary": primary,
        "flush_draw": flush_draw,
        "oesd": oesd,
        "made_flush": made_flush,
        "made_straight": straight,
        "made_full": made_full,
    }


def _validate_primary_groups(primary_groups: Dict[str, Sequence[str]], available_categories: Iterable[str]) -> None:
    available = set(available_categories)
    unknown = []
    for label, members in primary_groups.items():
        if not isinstance(members, (list, tuple, set)):
            raise TypeError(f"Group {label!r} must map to a list/tuple of categories.")
        for cat in members:
            if cat not in available:
                unknown.append((label, cat))
    if unknown:
        options = ", ".join(sorted(available))
        details = ", ".join(f"{label}:{cat}" for label, cat in unknown)
        raise ValueError(f"Unknown categories in PRIMARY_GROUPS: {details}. Available: {options}")
    mapped = set(cat for members in primary_groups.values() for cat in members)
    missing = [cat for cat in available if cat not in mapped]
    if missing:
        print(f"Warning: categories not mapped in PRIMARY_GROUPS and omitted from the table: {', '.join(sorted(missing))}")


def load_cbet_events(db_path: Path, cache_path: Path | None = None, force: bool = False) -> List[Dict]:
    if cache_path and cache_path.exists() and not force:
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached and ("in_position" not in cached[0] or "responses" not in cached[0]):
            return load_cbet_events(db_path, cache_path, force=True)
        return cached

    events: List[Dict] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories")
        for row in cur:
            root = ET.fromstring(row["HandHistory"])
            big_blind = _extract_big_blind(root)
            if big_blind is None or big_blind <= 0:
                continue
            players = [p.attrib.get("name") for p in root.findall('.//game/general/players/player')]
            if not players:
                continue
            pocket_cards = {}
            for node in root.findall('.//round[@no="1"]/cards'):
                player = node.attrib.get("player")
                cards = _parse_cards(node.text)
                if player and len(cards) == 2:
                    pocket_cards[player] = cards
            if not pocket_cards:
                continue

            total_pot = 0.0
            last_aggressor = None
            cbet_logged = False
            flop_cards: List[Tuple[str, int, str]] | None = None
            flop_players_set: set[str] = set()
            flop_actions: List[Tuple[str, str]] = []
            current_event: Dict | None = None
            responders_recorded: set[str] = set()
            flop_total_players: int | None = None

            rounds = sorted(root.findall('.//round'), key=lambda r: int(r.attrib.get('no', '0')))
            for rnd in rounds:
                round_no = int(rnd.attrib.get('no', '0'))
                if round_no == 2 and flop_cards is None:
                    for card_node in rnd.findall('cards'):
                        if card_node.attrib.get('type') == 'Flop':
                            flop_cards = _parse_cards(card_node.text)
                            break
                if round_no == 2 and flop_total_players is None:
                    players_this_round = {a.attrib.get('player') for a in rnd.findall('action') if a.attrib.get('player')}
                    flop_total_players = len(players_this_round)

                for action in rnd.findall('action'):
                    player = action.attrib.get('player')
                    if not player:
                        continue
                    act_type = action.attrib.get('type')
                    try:
                        amount = float(action.attrib.get('sum') or 0.0)
                    except ValueError:
                        amount = 0.0

                    if round_no == 1 and act_type in RAISE_TYPES and amount > 0:
                        last_aggressor = player
                    elif round_no == 2:
                        prior_actions = list(flop_actions)
                        flop_actions.append((player, act_type))
                        flop_players_set.add(player)
                        if not cbet_logged and last_aggressor and player == last_aggressor and act_type in BET_TYPES.union(RAISE_TYPES) and amount > 0:
                            if flop_cards and player in pocket_cards and total_pot > 0:
                                ratio = amount / total_pot
                                classification = _classify_hand(pocket_cards[player], flop_cards)
                                in_position = any(actor != last_aggressor for actor, _ in prior_actions)
                                event = {
                                    "hand_number": row["HandNumber"],
                                    "player": player,
                                    "ratio": round(ratio, 6),
                                    "primary": classification["primary"],
                                    "hole_cards": " ".join(card for _, _, card in pocket_cards[player]),
                                    "flop_cards": " ".join(card for _, _, card in flop_cards),
                                    "has_flush_draw": bool(classification["flush_draw"]),
                                    "has_oesd": bool(classification["oesd"]),
                                    "made_flush": bool(classification["made_flush"]),
                                    "made_straight": bool(classification["made_straight"]),
                                    "made_full_house": bool(classification["made_full"]),
                                    "in_position": bool(in_position),
                                    "flop_players": flop_total_players or len(flop_players_set),
                                    "responses": [],
                                }
                                events.append(event)
                                current_event = event
                                responders_recorded = set()
                            cbet_logged = True
                    if (
                        round_no == 2
                        and current_event is not None
                        and player != current_event["player"]
                        and player not in responders_recorded
                    ):
                        response_kind: str | None = None
                        if act_type in FOLD_TYPES:
                            response_kind = "Fold"
                        elif act_type in CALL_TYPES:
                            response_kind = "Call"
                        elif act_type in RAISE_TYPES:
                            response_kind = "Raise"
                        elif act_type in BET_TYPES:
                            response_kind = "Raise"

                        if response_kind:
                            current_event["responses"].append(
                                {
                                    "player": player,
                                    "action_type": act_type,
                                    "response": response_kind,
                                    "amount": amount,
                                }
                            )
                            responders_recorded.add(player)
                    if amount > 0:
                        total_pot += amount
                if round_no != 2:
                    current_event = None

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(events, fh, ensure_ascii=False, indent=2)

    return events


def summarize_events(
    events: List[Dict],
    buckets: List[Tuple[float, float, str]],
    primary_groups: Dict[str, Sequence[str]],
    draw_flag_map: Dict[str, str],
) -> List[Dict]:
    available_categories = sorted({event["primary"] for event in events})
    _validate_primary_groups(primary_groups, available_categories)

    summary: List[Dict] = []
    for low, high, label in buckets:
        subset = [event for event in events if low <= event["ratio"] < high]
        total = len(subset)
        row = {"Bucket": label, "Range": (low, high), "Events": total}

        if total:
            for group_name, members in primary_groups.items():
                count = sum(1 for event in subset if event["primary"] in members)
                row[group_name] = count / total * 100
            for draw_name, field in draw_flag_map.items():
                count = sum(1 for event in subset if event.get(field))
                row[draw_name] = count / total * 100
        else:
            for group_name in primary_groups:
                row[group_name] = 0.0
            for draw_name in draw_flag_map:
                row[draw_name] = 0.0

        summary.append(row)

    return summary


def display_summary(summary: List[Dict], primary_groups: Dict[str, Sequence[str]], draw_flag_map: Dict[str, str], digits: int = 1) -> None:
    if not summary:
        print("No events to display.")
        return

    bucket_width = max(len(row["Bucket"]) for row in summary + [{"Bucket": "Bucket"}])
    event_width = max(len(str(row["Events"])) for row in summary + [{"Events": "Events"}])
    header_names = list(primary_groups.keys()) + list(draw_flag_map.keys())

    header_line = f"{'Bucket':<{bucket_width}} {'Events':>{event_width}}"
    for name in header_names:
        header_line += f" {name:>12}"
    print(header_line)

    for row in summary:
        line = f"{row['Bucket']:<{bucket_width}} {row['Events']:>{event_width}d}"
        for name in primary_groups.keys():
            value = row.get(name, 0.0)
            line += f" {value:10.{digits}f}%"
        for name in draw_flag_map.keys():
            value = row.get(name, 0.0)
            line += f" {value:10.{digits}f}%"
        print(line)


def events_to_dataframe(events: List[Dict]):
    if pd is None:
        raise ImportError("pandas is not installed. Install pandas to work with the DataFrame helper.")
    return pd.DataFrame(events)


def available_primary_categories(events: List[Dict]) -> List[str]:
    return sorted({event["primary"] for event in events})


def response_events(events: List[Dict]) -> List[Dict]:
    """Flatten per-player responses to flop c-bets."""

    response_rows: List[Dict] = []
    for event in events:
        responses = event.get("responses") or []
        total_responses = len(responses)
        for order, response in enumerate(responses, start=1):
            response_rows.append(
                {
                    "hand_number": event.get("hand_number"),
                    "bettor": event.get("player"),
                    "ratio": event.get("ratio"),
                    "responder": response.get("player"),
                    "response": response.get("response"),
                    "response_order": order,
                    "response_amount": response.get("amount"),
                    "flop_players": event.get("flop_players"),
                    "responses_recorded": total_responses,
                    "bettor_in_position": event.get("in_position"),
                }
            )
    return response_rows
