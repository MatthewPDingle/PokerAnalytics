"""Unit tests for preflop shove services."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

from poker_analytics.services.preflop_shove import (
    ShoveEvent,
    get_equity_payload,
    get_shove_range_payload,
)


def _sample_events() -> List[ShoveEvent]:
    return [
        ShoveEvent(
            hand_number="H1",
            player="Hero1",
            category="First to Bet Shove",
            aggressive_level=1,
            hole_cards="HA HK",
            bet_amount=10.0,
            bet_amount_bb=20.0,
            pot_before=5.0,
            big_blind=0.5,
        ),
        ShoveEvent(
            hand_number="H2",
            player="Hero2",
            category="First to Bet Shove",
            aggressive_level=1,
            hole_cards="DA DK",
            bet_amount=40.0,
            bet_amount_bb=80.0,
            pot_before=6.0,
            big_blind=0.5,
        ),
        ShoveEvent(
            hand_number="H3",
            player="Hero3",
            category="3-Bet Shove",
            aggressive_level=2,
            hole_cards="SK HK",
            bet_amount=15.0,
            bet_amount_bb=30.0,
            pot_before=9.0,
            big_blind=0.5,
        ),
    ]


def test_get_shove_range_payload_basic() -> None:
    payload = get_shove_range_payload(_sample_events())
    assert len(payload) == 5

    leq30 = next(item for item in payload if item["id"] == "first_to_bet_leq30")
    gt30 = next(item for item in payload if item["id"] == "first_to_bet_gt30")
    three_bet = next(item for item in payload if item["id"] == "three_bet_shove")

    assert leq30["events"] == 1
    assert gt30["events"] == 1
    assert three_bet["events"] == 1

    grid = leq30["grid"]["values"]
    assert grid[0][0] == 100.0  # AA sits at row 0, col 0
    summary_primary = {row["group"]: row["percent"] for row in leq30["summary_primary"]}
    assert summary_primary["AA"] == 100.0


def test_get_equity_payload_from_cache() -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        cache_path = Path(tmp.name)
    try:
        sample = {
            "first_to_bet_leq30": {
                "equity_grid": {"A": {"A": 55.0}},
                "ev_grid": {"A": {"A": 1.5}},
                "call_amount_bb": 20,
                "villain_amount_bb": 18,
                "pot_before_bb": 5,
                "rake_percent": 5,
                "rake_cap_bb": 1,
                "trials_per_combo": 1000,
            }
        }
        cache_path.write_text(json.dumps(sample), encoding="utf-8")
        payload = get_equity_payload(cache_path=cache_path)
        assert len(payload) == 1
        item = payload[0]
        assert item["id"] == "first_to_bet_leq30"
        assert item["equity_grid"]["values"][0][0] == 55.0
        assert item["ev_grid"]["values"][0][0] == 1.5
        assert item["metadata"]["call_amount_bb"] == 20
    finally:
        cache_path.unlink(missing_ok=True)
