"""Lightweight parser for PokerStars text hand histories (cash NL10).

This importer is intentionally scoped for static population analyses:

- It extracts **flop**, **turn**, and **river** bet events needed to build
  bettor hand breakdowns (no hero concept).
- It ignores hands without a bet on the relevant street or where the bettor's
  hole cards are never shown at showdown.

Parsed events are shaped to match the expectations of the corresponding
matrix aggregators so they can be fed directly into:

- ``flop_hand_matrix._aggregate(...)`` → ``flop_hand_matrix_*`` caches.
- ``turn_hand_matrix._aggregate(...)`` → ``turn_hand_matrix_*`` caches.
- ``river_hand_matrix._aggregate(...)`` → ``river_hand_matrix_*`` caches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

from poker_analytics.data.flop_hand_categories import classify_flop_hand, parse_board_cards, parse_hole_cards
from poker_analytics.data.stakes import StakePolicy
from poker_analytics.data.textures import texture_keys
from poker_analytics.services.flop_bucket_utils import bucket_for_ratio, bucket_keys_for_event


@dataclass
class FlopBetEvent:
    hand_id: str
    bettor: str
    big_blind: float
    pot_before: float
    bet_amount: float
    board_text: str
    preflop_raise_count: int
    preflop_aggressor: Optional[str]
    player_count: int
    is_all_in: bool


@dataclass
class TurnBetEvent:
    hand_id: str
    bettor: str
    big_blind: float
    pot_before: float
    bet_amount: float
    board_text: str  # flop + turn cards, board-text format
    preflop_raise_count: int
    player_count: int
    is_all_in: bool


@dataclass
class RiverBetEvent:
    hand_id: str
    bettor: str
    big_blind: float
    pot_before: float
    bet_amount: float
    board_text: str  # flop + turn + river cards, board-text format
    preflop_raise_count: int
    player_count: int
    is_all_in: bool


HAND_HEADER_RE = re.compile(
    r"^PokerStars Hand #(?P<hand_id>\d+):\s+Hold'em No Limit\s+\(\$(?P<sb>\d+(?:\.\d+)?)/\$(?P<bb>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

TABLE_BUTTON_RE = re.compile(r"Seat #(?P<button>\d+)\s+is the button", re.IGNORECASE)
SEAT_RE = re.compile(r"^Seat\s+(?P<seat>\d+):\s+(?P<name>[^()]+?)\s+\(\$(?P<stack>\d+(?:\.\d+)?)\s+in chips\)", re.IGNORECASE)
POSTS_BLIND_RE = re.compile(r"^(?P<name>[^:]+):\s+posts\s+(small blind|big blind)\s+\$(?P<amount>\d+(?:\.\d+)?)", re.IGNORECASE)
CALLS_RE = re.compile(r"^(?P<name>[^:]+):\s+calls\s+\$(?P<amount>\d+(?:\.\d+)?)", re.IGNORECASE)
BETS_RE = re.compile(r"^(?P<name>[^:]+):\s+bets\s+\$(?P<amount>\d+(?:\.\d+)?)", re.IGNORECASE)
RAISES_RE = re.compile(
    r"^(?P<name>[^:]+):\s+raises\s+\$(?P<raise_amt>\d+(?:\.\d+)?)\s+to\s+\$(?P<total>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
FOLDS_RE = re.compile(r"^(?P<name>[^:]+):\s+folds\b", re.IGNORECASE)
FLOP_RE = re.compile(r"^\*\*\* FLOP \*\*\* \[(?P<cards>[^\]]+)\]", re.IGNORECASE)
TURN_RE = re.compile(r"^\*\*\* TURN \*\*\*", re.IGNORECASE)
TURN_BOARD_RE = re.compile(r"^\*\*\* TURN \*\*\* \[(?P<flop>[^\]]+)\] \[(?P<turn>[^\]]+)\]", re.IGNORECASE)
RIVER_BOARD_RE = re.compile(r"^\*\*\* RIVER \*\*\* \[(?P<flop_turn>[^\]]+)\] \[(?P<river>[^\]]+)\]", re.IGNORECASE)
SHOWDOWN_RE = re.compile(r"^\*\*\* SHOW DOWN \*\*\*", re.IGNORECASE)
SHOWS_RE = re.compile(r"^(?P<name>[^:]+):\s+shows\s+\[(?P<cards>[^\]]+)\]", re.IGNORECASE)


def _iter_hands(file_path: Path) -> Iterator[List[str]]:
    """Yield raw hands (list of lines) from a single HH file."""

    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return

    current: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if HAND_HEADER_RE.match(line):
            if current:
                yield current
                current = []
        if line or current:
            current.append(line)
    if current:
        yield current


def _normalise_cards_to_suit_rank(text: str) -> str:
    """Convert tokens like '7h' into 'H7' for compatibility with parse_hole_cards."""

    parts = [part for part in text.replace("\t", " ").split() if part]
    converted: List[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if len(token) == 2:
            rank, suit = token[0].upper(), token[1].upper()
            # Suit-rank already
            if suit in {"C", "D", "H", "S"} and rank.isdigit() or rank in {"T", "J", "Q", "K", "A"}:
                converted.append(f"{suit}{rank}")
            else:
                # Rank-suit (e.g. '7h')
                if rank in {"T", "J", "Q", "K", "A"} or rank.isdigit():
                    converted.append(f"{suit}{rank}")
                else:
                    # Fallback: keep raw token
                    converted.append(token.upper())
        else:
            converted.append(token.upper())
    return " ".join(converted)


def _extract_flop_bet_event(hand_lines: Sequence[str], stake_policy: StakePolicy) -> Optional[FlopBetEvent]:
    """Extract a single flop bet event (first flop bet) from a parsed hand."""

    if not hand_lines:
        return None

    header_match = HAND_HEADER_RE.match(hand_lines[0])
    if not header_match:
        return None

    hand_id = header_match.group("hand_id")
    try:
        big_blind = float(header_match.group("bb"))
    except (TypeError, ValueError):
        return None

    if not stake_policy.matches(big_blind):
        return None

    total_pot = 0.0
    preflop_raise_count = 0
    preflop_aggressor: Optional[str] = None
    active_players: set[str] = set()

    in_hole_cards = False
    in_flop = False
    flop_board_text: Optional[str] = None
    flop_pot_before: Optional[float] = None
    flop_player_count: Optional[int] = None
    flop_bet_recorded = False
    players_in_hand: set[str] = set()

    # Track preflop contributions so we can approximate pot size.
    player_contrib: Dict[str, float] = {}

    for line in hand_lines:
        if line.startswith("*** HOLE CARDS ***"):
            in_hole_cards = True
            continue
        if FLOP_RE.match(line):
            match = FLOP_RE.match(line)
            if not match:
                continue
            flop_board_text = match.group("cards")
            in_flop = True
            in_hole_cards = False
            flop_pot_before = total_pot
            flop_player_count = len(active_players) if active_players else None
            continue
        if TURN_RE.match(line) or SHOWDOWN_RE.match(line) or line.startswith("*** SUMMARY ***"):
            in_flop = False

        seat_match = SEAT_RE.match(line)
        if seat_match:
            name = seat_match.group("name").strip()
            players_in_hand.add(name)
            active_players.add(name)
            continue

        if not in_hole_cards and not in_flop:
            # Preflop blind posting and preflop actions before HOLE CARDS marker.
            blind_match = POSTS_BLIND_RE.match(line)
            if blind_match:
                name = blind_match.group("name").strip()
                amount = float(blind_match.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                active_players.add(name)
                continue

        if in_hole_cards and not in_flop:
            # Preflop actions.
            m = CALLS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount + prev - prev, 0.0)
                total_pot += delta
                player_contrib[name] = prev + amount
                active_players.add(name)
                continue
            m = RAISES_RE.match(line)
            if m:
                name = m.group("name").strip()
                total = float(m.group("total"))
                prev = player_contrib.get(name, 0.0)
                delta = max(total - prev, 0.0)
                total_pot += delta
                player_contrib[name] = total
                preflop_raise_count += 1
                preflop_aggressor = name
                active_players.add(name)
                continue
            m = BETS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                preflop_raise_count += 1
                preflop_aggressor = name
                active_players.add(name)
                continue
            m = FOLDS_RE.match(line)
            if m:
                name = m.group("name").strip()
                active_players.discard(name)
                continue

        if in_flop and flop_board_text is not None and flop_pot_before is not None and not flop_bet_recorded:
            m_raise = RAISES_RE.match(line)
            m_bet = BETS_RE.match(line)
            if m_raise or m_bet:
                name = (m_raise or m_bet).group("name").strip()
                if m_raise:
                    bet_amount = float(m_raise.group("total"))
                else:
                    bet_amount = float(m_bet.group("amount"))

                is_all_in = "all-in" in line.lower()

                # We only record the first flop bet event per hand.
                flop_bet_recorded = True
                if flop_player_count is None:
                    flop_player_count = len(active_players) if active_players else 0

                return FlopBetEvent(
                    hand_id=hand_id,
                    bettor=name,
                    big_blind=big_blind,
                    pot_before=flop_pot_before,
                    bet_amount=bet_amount,
                    board_text=flop_board_text,
                    preflop_raise_count=preflop_raise_count,
                    preflop_aggressor=preflop_aggressor,
                    player_count=flop_player_count or 0,
                    is_all_in=is_all_in,
                )

    return None


def _extract_turn_bet_event(hand_lines: Sequence[str], stake_policy: StakePolicy) -> Optional[TurnBetEvent]:
    """Extract a single turn bet event (first turn bet) from a parsed hand."""

    if not hand_lines:
        return None

    header_match = HAND_HEADER_RE.match(hand_lines[0])
    if not header_match:
        return None

    hand_id = header_match.group("hand_id")
    try:
        big_blind = float(header_match.group("bb"))
    except (TypeError, ValueError):
        return None

    if not stake_policy.matches(big_blind):
        return None

    total_pot = 0.0
    preflop_raise_count = 0
    active_players: set[str] = set()

    in_hole_cards = False
    in_flop = False
    in_turn = False

    turn_board_text: Optional[str] = None
    turn_pot_before: Optional[float] = None
    turn_player_count: Optional[int] = None

    # Track contributions across preflop + flop so we can approximate pot size.
    player_contrib: Dict[str, float] = {}

    for line in hand_lines:
        if line.startswith("*** HOLE CARDS ***"):
            in_hole_cards = True
            continue

        flop_match = FLOP_RE.match(line)
        if flop_match:
            in_flop = True
            in_hole_cards = False
            continue

        turn_board_match = TURN_BOARD_RE.match(line)
        if turn_board_match:
            in_flop = False
            in_turn = True
            # Combine flop and turn cards into a single board-text string.
            flop_cards_text = turn_board_match.group("flop")
            turn_card_text = turn_board_match.group("turn")
            turn_board_text = f"{flop_cards_text} {turn_card_text}"
            turn_pot_before = total_pot
            turn_player_count = len(active_players) if active_players else 0
            continue

        if RIVER_BOARD_RE.match(line) or SHOWDOWN_RE.match(line) or line.startswith("*** SUMMARY ***"):
            in_turn = False

        seat_match = SEAT_RE.match(line)
        if seat_match:
            name = seat_match.group("name").strip()
            active_players.add(name)
            continue

        # Preflop blind posting and preflop actions before HOLE CARDS marker.
        if not in_hole_cards and not in_flop and not in_turn:
            blind_match = POSTS_BLIND_RE.match(line)
            if blind_match:
                name = blind_match.group("name").strip()
                amount = float(blind_match.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                active_players.add(name)
                continue

        # Preflop actions.
        if in_hole_cards and not in_flop and not in_turn:
            m = CALLS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount, 0.0)
                total_pot += delta
                player_contrib[name] = prev + amount
                active_players.add(name)
                continue
            m = RAISES_RE.match(line)
            if m:
                name = m.group("name").strip()
                total = float(m.group("total"))
                prev = player_contrib.get(name, 0.0)
                delta = max(total - prev, 0.0)
                total_pot += delta
                player_contrib[name] = total
                preflop_raise_count += 1
                active_players.add(name)
                continue
            m = BETS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                preflop_raise_count += 1
                active_players.add(name)
                continue
            m = FOLDS_RE.match(line)
            if m:
                name = m.group("name").strip()
                active_players.discard(name)
                continue

        # Flop actions (contribute to pot size on turn).
        if in_flop and not in_turn:
            m = CALLS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                total_pot += max(amount, 0.0)
                active_players.add(name)
                continue
            m = RAISES_RE.match(line)
            if m:
                name = m.group("name").strip()
                total = float(m.group("total"))
                # We don't track per-street contribs separately here; treat the
                # stated total as the amount added on this street.
                total_pot += max(total, 0.0)
                active_players.add(name)
                continue
            m = BETS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                total_pot += max(amount, 0.0)
                active_players.add(name)
                continue
            m = FOLDS_RE.match(line)
            if m:
                name = m.group("name").strip()
                active_players.discard(name)
                continue

        # First turn bet.
        if in_turn and turn_board_text is not None and turn_pot_before is not None:
            m_raise = RAISES_RE.match(line)
            m_bet = BETS_RE.match(line)
            if m_raise or m_bet:
                name = (m_raise or m_bet).group("name").strip()
                if m_raise:
                    bet_amount = float(m_raise.group("total"))
                else:
                    bet_amount = float(m_bet.group("amount"))

                is_all_in = "all-in" in line.lower()
                if turn_player_count is None:
                    turn_player_count = len(active_players) if active_players else 0

                return TurnBetEvent(
                    hand_id=hand_id,
                    bettor=name,
                    big_blind=big_blind,
                    pot_before=turn_pot_before,
                    bet_amount=bet_amount,
                    board_text=turn_board_text,
                    preflop_raise_count=preflop_raise_count,
                    player_count=turn_player_count or 0,
                    is_all_in=is_all_in,
                )

    return None


def _extract_river_bet_event(hand_lines: Sequence[str], stake_policy: StakePolicy) -> Optional[RiverBetEvent]:
    """Extract a single river bet event (first river bet) from a parsed hand."""

    if not hand_lines:
        return None

    header_match = HAND_HEADER_RE.match(hand_lines[0])
    if not header_match:
        return None

    hand_id = header_match.group("hand_id")
    try:
        big_blind = float(header_match.group("bb"))
    except (TypeError, ValueError):
        return None

    if not stake_policy.matches(big_blind):
        return None

    total_pot = 0.0
    preflop_raise_count = 0
    active_players: set[str] = set()

    in_hole_cards = False
    in_flop = False
    in_turn = False
    in_river = False

    river_board_text: Optional[str] = None
    river_pot_before: Optional[float] = None
    river_player_count: Optional[int] = None

    player_contrib: Dict[str, float] = {}

    for line in hand_lines:
        if line.startswith("*** HOLE CARDS ***"):
            in_hole_cards = True
            continue

        flop_match = FLOP_RE.match(line)
        if flop_match:
            in_flop = True
            in_hole_cards = False
            continue

        turn_match = TURN_BOARD_RE.match(line)
        if turn_match:
            in_flop = False
            in_turn = True
            continue

        river_board_match = RIVER_BOARD_RE.match(line)
        if river_board_match:
            in_turn = False
            in_river = True
            flop_turn_cards_text = river_board_match.group("flop_turn")
            river_card_text = river_board_match.group("river")
            river_board_text = f"{flop_turn_cards_text} {river_card_text}"
            river_pot_before = total_pot
            river_player_count = len(active_players) if active_players else 0
            continue

        if SHOWDOWN_RE.match(line) or line.startswith("*** SUMMARY ***"):
            in_river = False

        seat_match = SEAT_RE.match(line)
        if seat_match:
            name = seat_match.group("name").strip()
            active_players.add(name)
            continue

        # Preflop blind posting and actions.
        if not in_hole_cards and not in_flop and not in_turn and not in_river:
            blind_match = POSTS_BLIND_RE.match(line)
            if blind_match:
                name = blind_match.group("name").strip()
                amount = float(blind_match.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                active_players.add(name)
                continue

        if in_hole_cards and not in_flop and not in_turn and not in_river:
            m = CALLS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount, 0.0)
                total_pot += delta
                player_contrib[name] = prev + amount
                active_players.add(name)
                continue
            m = RAISES_RE.match(line)
            if m:
                name = m.group("name").strip()
                total = float(m.group("total"))
                prev = player_contrib.get(name, 0.0)
                delta = max(total - prev, 0.0)
                total_pot += delta
                player_contrib[name] = total
                preflop_raise_count += 1
                active_players.add(name)
                continue
            m = BETS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                prev = player_contrib.get(name, 0.0)
                delta = max(amount - prev, 0.0)
                total_pot += delta
                player_contrib[name] = amount
                preflop_raise_count += 1
                active_players.add(name)
                continue
            m = FOLDS_RE.match(line)
            if m:
                name = m.group("name").strip()
                active_players.discard(name)
                continue

        # Flop + turn actions contribute to pot sizing.
        if in_flop or in_turn:
            m = CALLS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                total_pot += max(amount, 0.0)
                active_players.add(name)
                continue
            m = RAISES_RE.match(line)
            if m:
                name = m.group("name").strip()
                total = float(m.group("total"))
                total_pot += max(total, 0.0)
                active_players.add(name)
                continue
            m = BETS_RE.match(line)
            if m:
                name = m.group("name").strip()
                amount = float(m.group("amount"))
                total_pot += max(amount, 0.0)
                active_players.add(name)
                continue
            m = FOLDS_RE.match(line)
            if m:
                name = m.group("name").strip()
                active_players.discard(name)
                continue

        # First river bet.
        if in_river and river_board_text is not None and river_pot_before is not None:
            m_raise = RAISES_RE.match(line)
            m_bet = BETS_RE.match(line)
            if m_raise or m_bet:
                name = (m_raise or m_bet).group("name").strip()
                if m_raise:
                    bet_amount = float(m_raise.group("total"))
                else:
                    bet_amount = float(m_bet.group("amount"))

                is_all_in = "all-in" in line.lower()
                if river_player_count is None:
                    river_player_count = len(active_players) if active_players else 0

                return RiverBetEvent(
                    hand_id=hand_id,
                    bettor=name,
                    big_blind=big_blind,
                    pot_before=river_pot_before,
                    bet_amount=bet_amount,
                    board_text=river_board_text,
                    preflop_raise_count=preflop_raise_count,
                    player_count=river_player_count or 0,
                    is_all_in=is_all_in,
                )

    return None


def _extract_shown_cards(hand_lines: Sequence[str]) -> Dict[str, str]:
    """Return a mapping of player name -> hole cards text (suit-rank format)."""

    shown: Dict[str, str] = {}
    in_showdown = False

    for line in hand_lines:
        if SHOWDOWN_RE.match(line):
            in_showdown = True
            continue
        if line.startswith("*** SUMMARY ***"):
            in_showdown = False
        if not in_showdown:
            continue
        match = SHOWS_RE.match(line)
        if not match:
            continue
        name = match.group("name").strip()
        raw_cards = match.group("cards")
        shown[name] = _normalise_cards_to_suit_rank(raw_cards)

    return shown


def collect_pokerstars_flop_events(root: Path, stake_policy: Optional[StakePolicy] = None) -> List[Mapping[str, object]]:
    """Collect flop bet events from all PokerStars HH files under ``root``.

    The returned events are suitable for feeding into
    ``flop_hand_matrix._aggregate``.
    """

    stake_policy = stake_policy or StakePolicy.from_environment()

    events: List[Mapping[str, object]] = []

    for path in sorted(root.glob("*.txt")):
        for hand_lines in _iter_hands(path):
            bet_event = _extract_flop_bet_event(hand_lines, stake_policy)
            if bet_event is None:
                continue

            shown_cards = _extract_shown_cards(hand_lines)
            hole_text = shown_cards.get(bet_event.bettor)
            if not hole_text:
                continue

            board_suit_rank = _normalise_cards_to_suit_rank(bet_event.board_text)
            hole_cards = parse_hole_cards(hole_text)
            board_cards = parse_board_cards(board_suit_rank)
            if not hole_cards or not board_cards:
                continue

            classification = classify_flop_hand(hole_cards, board_cards)

            pot_before = bet_event.pot_before
            if pot_before <= 0:
                continue
            ratio = bet_event.bet_amount / pot_before

            bucket = bucket_for_ratio(ratio)
            bucket_key = bucket.key if bucket is not None else None
            is_one_bb = bet_event.big_blind > 0 and abs(bet_event.bet_amount - bet_event.big_blind) <= max(
                1e-6, bet_event.big_blind * 1e-4
            )

            bucket_payload = {
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": bet_event.is_all_in,
                "is_one_bb": is_one_bb,
            }
            bucket_keys = bucket_keys_for_event(bucket_payload)
            if not bucket_keys:
                continue

            event_record = {
                "hero_position": "UNKNOWN",
                "bet_type": "cbet" if bet_event.preflop_aggressor == bet_event.bettor else "stab",
                "in_position": False,
                "player_count": bet_event.player_count or 0,
                "flop_cards": board_suit_rank,
                "flop_texture_keys": texture_keys(bet_event.board_text),
                "preflop_aggression_level": bet_event.preflop_raise_count,
                "preflop_bucket_key": None,
                "spr_bucket": None,
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": bet_event.is_all_in,
                "is_one_bb": is_one_bb,
                "hand_primary": classification.primary,
                "has_flush_draw": classification.has_flush_draw,
                "has_oesd_dg": classification.has_oesd_dg,
            }
            events.append(event_record)

    return events


def _build_bucket_payload(
    *,
    big_blind: float,
    pot_before: float,
    bet_amount: float,
    is_all_in: bool,
) -> tuple[Optional[str], float, bool, bool]:
    """Helper to compute bucket key + flags for a bet event."""

    if pot_before <= 0:
        return None, 0.0, False, False

    ratio = bet_amount / pot_before
    bucket = bucket_for_ratio(ratio)
    bucket_key = bucket.key if bucket is not None else None
    is_one_bb = big_blind > 0 and abs(bet_amount - big_blind) <= max(1e-6, big_blind * 1e-4)
    return bucket_key, ratio, is_all_in, is_one_bb


def collect_pokerstars_turn_events(root: Path, stake_policy: Optional[StakePolicy] = None) -> List[Mapping[str, object]]:
    """Collect turn bet events from all PokerStars HH files under ``root``.

    The returned events are suitable for feeding into
    ``turn_hand_matrix._aggregate``.
    """

    stake_policy = stake_policy or StakePolicy.from_environment()

    events: List[Mapping[str, object]] = []

    for path in sorted(root.glob("*.txt")):
        for hand_lines in _iter_hands(path):
            bet_event = _extract_turn_bet_event(hand_lines, stake_policy)
            if bet_event is None:
                continue

            shown_cards = _extract_shown_cards(hand_lines)
            hole_text = shown_cards.get(bet_event.bettor)
            if not hole_text:
                continue

            board_suit_rank = _normalise_cards_to_suit_rank(bet_event.board_text)
            hole_cards = parse_hole_cards(hole_text)
            board_cards = parse_board_cards(board_suit_rank)
            if not hole_cards or not board_cards:
                continue

            classification = classify_flop_hand(hole_cards, board_cards)

            bucket_key, ratio, is_all_in, is_one_bb = _build_bucket_payload(
                big_blind=bet_event.big_blind,
                pot_before=bet_event.pot_before,
                bet_amount=bet_event.bet_amount,
                is_all_in=bet_event.is_all_in,
            )
            if bucket_key is None or ratio <= 0:
                continue

            bucket_payload = {
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": is_all_in,
                "is_one_bb": is_one_bb,
            }
            bucket_keys = bucket_keys_for_event(bucket_payload)
            if not bucket_keys:
                continue

            event_record = {
                "hero_position": "UNKNOWN",
                # Line classification not currently available for PokerStars import;
                # leave bet_line empty so these events participate only in the
                # "any line" aggregates.
                "bet_line": "",
                "in_position": False,
                "player_count": bet_event.player_count or 0,
                "turn_cards": board_suit_rank,
                "preflop_aggression_level": bet_event.preflop_raise_count,
                "spr_bucket": None,
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": is_all_in,
                "is_one_bb": is_one_bb,
                "hand_primary": classification.primary,
                "has_flush_draw": getattr(classification, "has_flush_draw", False),
                "has_oesd_dg": getattr(classification, "has_oesd_dg", False),
            }
            events.append(event_record)

    return events


def collect_pokerstars_river_events(root: Path, stake_policy: Optional[StakePolicy] = None) -> List[Mapping[str, object]]:
    """Collect river bet events from all PokerStars HH files under ``root``.

    The returned events are suitable for feeding into
    ``river_hand_matrix._aggregate``.
    """

    stake_policy = stake_policy or StakePolicy.from_environment()

    events: List[Mapping[str, object]] = []

    for path in sorted(root.glob("*.txt")):
        for hand_lines in _iter_hands(path):
            bet_event = _extract_river_bet_event(hand_lines, stake_policy)
            if bet_event is None:
                continue

            shown_cards = _extract_shown_cards(hand_lines)
            hole_text = shown_cards.get(bet_event.bettor)
            if not hole_text:
                continue

            board_suit_rank = _normalise_cards_to_suit_rank(bet_event.board_text)
            hole_cards = parse_hole_cards(hole_text)
            board_cards = parse_board_cards(board_suit_rank)
            if not hole_cards or not board_cards:
                continue

            classification = classify_flop_hand(hole_cards, board_cards)

            bucket_key, ratio, is_all_in, is_one_bb = _build_bucket_payload(
                big_blind=bet_event.big_blind,
                pot_before=bet_event.pot_before,
                bet_amount=bet_event.bet_amount,
                is_all_in=bet_event.is_all_in,
            )
            if bucket_key is None or ratio <= 0:
                continue

            bucket_payload = {
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": is_all_in,
                "is_one_bb": is_one_bb,
            }
            bucket_keys = bucket_keys_for_event(bucket_payload)
            if not bucket_keys:
                continue

            event_record = {
                "hero_position": "UNKNOWN",
                "bet_line": "",
                "in_position": False,
                "player_count": bet_event.player_count or 0,
                "river_cards": board_suit_rank,
                "preflop_aggression_level": bet_event.preflop_raise_count,
                "spr_bucket": None,
                "bucket_key": bucket_key,
                "ratio": ratio,
                "is_check": False,
                "is_all_in": is_all_in,
                "is_one_bb": is_one_bb,
                "hand_primary": classification.primary,
                "has_flush_draw": getattr(classification, "has_flush_draw", False),
                "has_oesd_dg": getattr(classification, "has_oesd_dg", False),
            }
            events.append(event_record)

    return events


__all__ = [
    "collect_pokerstars_flop_events",
    "collect_pokerstars_turn_events",
    "collect_pokerstars_river_events",
]
