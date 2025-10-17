"""Tests for preflop response curve services."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from poker_analytics.services.preflop_response_curves import (
    ResponseCurveScenario,
    get_response_curve_payload,
    load_response_curve_scenarios,
)


def test_get_response_curve_payload_returns_sample_when_cache_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "response.json"
        payload = get_response_curve_payload(cache_path=cache_path)
        assert len(payload) >= 1
        scenario = payload[0]
        assert {
            "id",
            "points",
            "sample_size",
            "stack_bucket_key",
            "players_behind",
            "pot_bucket_key",
        }.issubset(scenario.keys())
        assert scenario["points"]
        first_point = scenario["points"][0]
        assert {"bucket_key", "bucket_label", "ev_bb"}.issubset(first_point.keys())


def test_load_response_curve_scenarios_prefers_cache() -> None:
    custom = [
        {
            "id": "cache_fixture",
            "hero_position": "BTN",
            "villain_profile": "Test Pool",
            "stack_depth": "30-60 bb",
            "situation_key": "facing_open",
            "situation_label": "Facing open raise",
            "players_to_act": 2,
            "pot_size_bb": 3.5,
            "sample_size": 123,
            "points": [
                {
                    "bucket_key": "pct_25_40",
                    "bucket_label": "25-40%",
                    "representative_ratio": 0.325,
                    "fold_pct": 20.0,
                    "call_pct": 55.0,
                    "raise_pct": 25.0,
                    "ev_bb": 2.5,
                },
            ],
        }
    ]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        cache_path = Path(tmp.name)
    try:
        cache_path.write_text(json.dumps(custom), encoding="utf-8")
        scenarios = load_response_curve_scenarios(cache_path=cache_path)
        assert len(scenarios) == 1
        scenario = scenarios[0]
        assert isinstance(scenario, ResponseCurveScenario)
        assert scenario.id == "cache_fixture"
        assert scenario.stack_bucket_key == "bb_30_60"
        assert scenario.players_behind == 2
        assert scenario.pot_bucket_key == "pot_medium"
        assert scenario.effective_stack_bb > 0
        assert scenario.points[0].ev_bb == 2.5

        payload = get_response_curve_payload(cache_path=cache_path)
        assert payload[0]["id"] == "cache_fixture"
        assert payload[0]["players_behind"] == 2
        assert payload[0]["stack_bucket_key"] == "bb_30_60"
        assert payload[0]["points"][0]["ev_bb"] == 2.5
    finally:
        cache_path.unlink(missing_ok=True)
