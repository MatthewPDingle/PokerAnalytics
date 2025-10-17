"""Preflop shove analysis loaders and aggregations."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from poker_analytics.config import build_data_paths
from poker_analytics.data.cards import CARD_RANKS, SUITS, extract_big_blind, parse_cards_text
from poker_analytics.data.drivehud import DriveHudDataSource

BET_TYPES = {"5", "7"}
RAISE_TYPES = {"23", "7"}

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
RANK_INDEX = {rank: idx for idx, rank in enumerate(RANKS)}

CATEGORY_LABELS = {
    1: "First to Bet Shove",
    2: "3-Bet Shove",
    3: "4-Bet Shove",
    4: "5+ Bet Shove",
}

RANGE_DEFINITIONS = [
    {
        "id": "first_to_bet_leq30",
        "category": "First to Bet Shove",
        "label": "First to Bet Shove (≤30 BB)",
        "max_bb": 30.0,
    },
    {
        "id": "first_to_bet_gt30",
        "category": "First to Bet Shove",
        "label": "First to Bet Shove (>30 BB)",
        "min_bb": 30.0,
    },
    {
        "id": "three_bet_shove",
        "category": "3-Bet Shove",
        "label": "3-Bet Shove",
    },
    {
        "id": "four_bet_shove",
        "category": "4-Bet Shove",
        "label": "4-Bet Shove",
    },
    {
        "id": "five_plus_bet_shove",
        "category": "5+ Bet Shove",
        "label": "5+ Bet Shove",
    },
]

HAND_GROUPS_ORDER = [
    "AA",
    "KK",
    "QQ",
    "JJ",
    "TT",
    "Other Pair",
    "AK",
    "ATs - AQs",
    "A2s - A9s",
    "ATo - AQo",
    "A2o - A9o",
    "Other Broadway Pair",
    "Other",
]

SUMMARY2_GROUPS_ORDER = [
    "KK - AA",
    "TT - QQ",
    "22 - 99",
    "AK",
    "Any Other Ace",
    "All Others",
]

BROADWAY_RANKS = {"A", "K", "Q", "J", "T"}
BROADWAY_COMBOS = {
    frozenset({"K", "Q"}),
    frozenset({"K", "J"}),
    frozenset({"K", "T"}),
    frozenset({"Q", "J"}),
    frozenset({"Q", "T"}),
    frozenset({"J", "T"}),
}


@dataclass(frozen=True)
class ShoveEvent:
    hand_number: str
    player: str
    category: str
    aggressive_level: int
    hole_cards: str
    bet_amount: float
    bet_amount_bb: Optional[float]
    pot_before: Optional[float]
    big_blind: float


def _categorise_shove(level: int) -> Optional[str]:
    if level <= 0:
        return None
    if level == 1:
        return CATEGORY_LABELS[1]
    if level == 2:
        return CATEGORY_LABELS[2]
    if level == 3:
        return CATEGORY_LABELS[3]
    return CATEGORY_LABELS[4]


def _is_all_in(action: ET.Element) -> bool:
    if action.attrib.get("type") == "7":
        return True
    return action.attrib.get("allin", "").lower() in {"1", "true", "yes"}


def _collect_preflop_actions(root: ET.Element) -> List[ET.Element]:
    actions: List[ET.Element] = []
    for round_node in root.findall(".//round"):
        if round_node.attrib.get("no") == "1":
            actions.extend(round_node.findall("action"))
    return actions


def load_preflop_shove_events(
    source: Optional[DriveHudDataSource] = None,
    *,
    cache_path: Optional[Path] = None,
    force: bool = False,
) -> List[ShoveEvent]:
    """Materialise shove events from the DriveHUD database (with optional caching)."""

    source = source or DriveHudDataSource.from_defaults()
    cache_path = cache_path or (build_data_paths().cache_dir / "preflop_shove_events.json")

    if not force and cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as fh:
            cached = json.load(fh)
        return [ShoveEvent(**event) for event in cached]

    if not source.is_available():
        return []

    events: List[ShoveEvent] = []
    query = "SELECT HandHistoryId, HandNumber, HandHistory FROM HandHistories"
    for row in source.rows(query):
        hand_xml = row.get("HandHistory")
        if not isinstance(hand_xml, str):
            continue
        try:
            root = ET.fromstring(hand_xml)
        except ET.ParseError:
            continue

        big_blind = extract_big_blind(root)
        if not big_blind:
            continue

        pocket_cards: Dict[str, List[tuple[str, int, str]]] = {}
        for node in root.findall('.//round[@no="1"]/cards'):
            player = node.attrib.get("player")
            cards = parse_cards_text(node.text)
            if player and len(cards) == 2:
                pocket_cards[player] = cards
        if not pocket_cards:
            continue

        aggressive_level = 0
        total_pot = 0.0
        actions = _collect_preflop_actions(root)
        if not actions:
            continue

        for action in actions:
            player = action.attrib.get("player")
            if not player:
                continue
            act_type = action.attrib.get("type")
            amount_text = action.attrib.get("sum") or action.attrib.get("bet") or "0"
            try:
                amount = float(amount_text)
            except ValueError:
                amount = 0.0

            if amount > 0:
                total_pot += amount

            if act_type not in BET_TYPES.union(RAISE_TYPES):
                continue
            if amount <= 0:
                continue

            aggressive_level += 1
            if not _is_all_in(action):
                continue

            category = _categorise_shove(aggressive_level)
            if category is None:
                continue

            hero_cards = pocket_cards.get(player)
            if not hero_cards:
                continue

            hole_cards = " ".join(card for _, _, card in hero_cards)
            pot_before = total_pot - amount if total_pot >= amount else 0.0
            events.append(
                ShoveEvent(
                    hand_number=str(row.get("HandNumber", "")),
                    player=player,
                    category=category,
                    aggressive_level=aggressive_level,
                    hole_cards=hole_cards,
                    bet_amount=amount,
                    bet_amount_bb=amount / big_blind if big_blind else None,
                    pot_before=pot_before,
                    big_blind=big_blind,
                )
            )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump([event.__dict__ for event in events], fh, ensure_ascii=False, indent=2)
    return events


def _parse_hole_cards(hole_cards: str) -> Optional[tuple[tuple[str, str], tuple[str, str]]]:
    tokens = [token.strip() for token in hole_cards.split() if token.strip()]
    if len(tokens) != 2:
        return None
    parsed = []
    for token in tokens:
        if len(token) != 2:
            return None
        suit, rank = token[0].upper(), token[1].upper()
        if suit not in SUITS or rank not in CARD_RANKS:
            return None
        parsed.append((rank, suit))
    return parsed[0], parsed[1]


def _grid_position(cards: tuple[tuple[str, str], tuple[str, str]]) -> tuple[str, str]:
    (rank_a, suit_a), (rank_b, suit_b) = cards
    if rank_a == rank_b:
        return rank_a, rank_a
    ranks = sorted([rank_a, rank_b], key=lambda r: RANK_INDEX[r])
    high, low = ranks[0], ranks[1]
    suited = suit_a == suit_b
    if suited:
        return high, low
    return low, high


def _classify_hand_group(cards: tuple[tuple[str, str], tuple[str, str]]) -> tuple[str, str]:
    (rank_a, suit_a), (rank_b, suit_b) = cards
    if rank_a == rank_b:
        rank = rank_a
        if rank == "A":
            return "AA", "KK - AA"
        if rank == "K":
            return "KK", "KK - AA"
        if rank == "Q":
            return "QQ", "TT - QQ"
        if rank == "J":
            return "JJ", "TT - QQ"
        if rank == "T":
            return "TT", "TT - QQ"
        if rank in {"9", "8", "7", "6", "5", "4", "3", "2"}:
            return "Other Pair", "22 - 99"
        if rank in BROADWAY_RANKS:
            return "Other Broadway Pair", "All Others"
        return "Other Pair", "All Others"

    suited = suit_a == suit_b
    combo = frozenset({rank_a, rank_b})
    if combo == frozenset({"A", "K"}):
        return "AK", "AK"
    if "A" in combo:
        other = next(iter(combo - {"A"}))
        if suited:
            if other in {"T", "J", "Q"}:
                return "ATs - AQs", "Any Other Ace"
            if other in {"2", "3", "4", "5", "6", "7", "8", "9"}:
                return "A2s - A9s", "Any Other Ace"
        else:
            if other in {"T", "J", "Q"}:
                return "ATo - AQo", "Any Other Ace"
            if other in {"2", "3", "4", "5", "6", "7", "8", "9"}:
                return "A2o - A9o", "Any Other Ace"
    if combo in BROADWAY_COMBOS:
        return "Other Broadway Pair", "All Others"
    return "Other", "All Others"


def _build_grid(events: Iterable[ShoveEvent]) -> tuple[Dict[str, Dict[str, float]], float]:
    grid = {row: {col: 0.0 for col in RANKS} for row in RANKS}
    total = 0.0
    for event in events:
        parsed = _parse_hole_cards(event.hole_cards)
        if parsed is None:
            continue
        row, col = _grid_position(parsed)
        grid[row][col] += 1
        total += 1
    return grid, total


def _build_summaries(events: Iterable[ShoveEvent]) -> tuple[List[dict], List[dict], float]:
    counts_primary = Counter({group: 0 for group in HAND_GROUPS_ORDER})
    counts_secondary = Counter({group: 0 for group in SUMMARY2_GROUPS_ORDER})
    total = 0
    for event in events:
        parsed = _parse_hole_cards(event.hole_cards)
        if parsed is None:
            continue
        label_primary, label_secondary = _classify_hand_group(parsed)
        counts_primary[label_primary] += 1
        counts_secondary[label_secondary] += 1
        total += 1

    summary_primary = [
        {
            "group": group,
            "percent": (counts_primary[group] / total * 100.0) if total else 0.0,
        }
        for group in HAND_GROUPS_ORDER
    ]
    summary_secondary = [
        {
            "group": group,
            "percent": (counts_secondary[group] / total * 100.0) if total else 0.0,
        }
        for group in SUMMARY2_GROUPS_ORDER
    ]
    return summary_primary, summary_secondary, float(total)


def _filter_events(
    events: Iterable[ShoveEvent],
    *,
    category: str,
    min_bb: float | None = None,
    max_bb: float | None = None,
) -> List[ShoveEvent]:
    filtered: List[ShoveEvent] = []
    for event in events:
        if event.category != category:
            continue
        bet_bb = event.bet_amount_bb or 0.0
        if min_bb is not None and bet_bb <= min_bb:
            continue
        if max_bb is not None and bet_bb > max_bb:
            continue
        filtered.append(event)
    return filtered


def get_shove_range_payload(events: Optional[List[ShoveEvent]] = None) -> List[dict]:
    events = events or load_preflop_shove_events()
    if not events:
        return []

    payload: List[dict] = []
    for definition in RANGE_DEFINITIONS:
        subset = _filter_events(
            events,
            category=definition["category"],
            min_bb=definition.get("min_bb"),
            max_bb=definition.get("max_bb"),
        )
        grid, total = _build_grid(subset)
        summary_primary, summary_secondary, summary_total = _build_summaries(subset)
        values: List[List[float]] = []
        for row in RANKS:
            row_values = []
            for col in RANKS:
                count = grid[row][col]
                pct = (count / total * 100.0) if total else 0.0
                row_values.append(round(pct, 3))
            values.append(row_values)
        payload.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "category": definition["category"],
                "events": int(total),
                "grid": {"rows": RANKS, "cols": RANKS, "values": values},
                "summary_primary": summary_primary,
                "summary_secondary": summary_secondary,
                "summary_events": int(summary_total),
            }
        )
    return payload


def _load_equity_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _grid_dict_to_matrix(grid: Dict[str, Dict[str, float]]) -> List[List[float]]:
    return [[float(grid.get(row, {}).get(col, 0.0)) for col in RANKS] for row in RANKS]


def get_equity_payload(cache_path: Optional[Path] = None) -> List[dict]:
    data_paths = build_data_paths()
    cache_path = cache_path or data_paths.cache_dir / "preflop_equity.json"
    if not cache_path.exists():
        legacy_path = Path("analysis/cache/preflop_equity.json")
        if legacy_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(legacy_path.read_text(), encoding="utf-8")
    cache = _load_equity_cache(cache_path)
    if not cache:
        return []

    label_map = {item["id"]: item["label"] for item in RANGE_DEFINITIONS}
    payload: List[dict] = []
    for key, scenario in cache.items():
        equity_grid = scenario.get("equity_grid")
        ev_grid = scenario.get("ev_grid")
        payload.append(
            {
                "id": key,
                "label": label_map.get(key, key.replace("_", " ").title()),
                "equity_grid": {
                    "rows": RANKS,
                    "cols": RANKS,
                    "values": _grid_dict_to_matrix(equity_grid) if equity_grid else [],
                },
                "ev_grid": {
                    "rows": RANKS,
                    "cols": RANKS,
                    "values": _grid_dict_to_matrix(ev_grid) if ev_grid else [],
                },
                "metadata": {
                    "call_amount_bb": scenario.get("call_amount_bb"),
                    "villain_amount_bb": scenario.get("villain_amount_bb"),
                    "pot_before_bb": scenario.get("pot_before_bb"),
                    "rake_percent": scenario.get("rake_percent"),
                    "rake_cap_bb": scenario.get("rake_cap_bb"),
                    "trials_per_combo": scenario.get("trials_per_combo"),
                },
            }
        )
    return payload


__all__ = [
    "ShoveEvent",
    "load_preflop_shove_events",
    "get_shove_range_payload",
    "get_equity_payload",
]
