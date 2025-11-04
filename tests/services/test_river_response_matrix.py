"""Tests for river response matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.river_response_matrix import (
    build_river_pot_contribution_payload,
    build_river_response_payload,
)

class RiverResponseMatrixTests(unittest.TestCase):
    def test_aggregation_counts_events_and_outcomes(self) -> None:
        events = [
            {
                "bet_line": "triple_barrel",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.55,
                "bucket_key": "pct_40_60",
                "is_check": False,
                "is_all_in": False,
                "is_one_bb": False,
                "villain_outcome": "fold",
                "total_added_river_bb": 4.0,
                "total_added_all_bb": 6.0,
                "pot_before_bb": 7.5,
                "hero_position": "BTN",
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 1,
            },
            {
                "bet_line": "triple_barrel",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.6,
                "bucket_key": "pct_40_60",
                "is_check": False,
                "is_all_in": False,
                "is_one_bb": False,
                "villain_outcome": "call",
                "total_added_river_bb": 4.5,
                "total_added_all_bb": 6.5,
                "pot_before_bb": 7.5,
                "hero_position": "BTN",
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 1,
            },
            {
                "bet_line": "river_stab",
                "position": "IP",
                "player_count": 3,
                "ratio": 0.3,
                "bucket_key": "pct_25_40",
                "is_check": False,
                "is_all_in": False,
                "is_one_bb": False,
                "villain_outcome": "raise",
                "total_added_river_bb": 3.0,
                "total_added_all_bb": 5.0,
                "pot_before_bb": 9.0,
                "hero_position": "CO",
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 2,
            },
        ]

        payload = build_river_response_payload(events)

        self.assertEqual(payload["version"], 1)
        bucket_keys = [bucket["key"] for bucket in payload["bucket_order"]]
        self.assertIn("pct_40_60", bucket_keys)
        self.assertIn("pct_25_40", bucket_keys)
        self.assertIn("betting_lines", payload)
        bet_line_keys = [entry["key"] for entry in payload["betting_lines"]]
        self.assertIn("triple_barrel", bet_line_keys)
        self.assertIn("river_stab", bet_line_keys)

        scenarios = payload["scenarios"]
        double_barrel = next(
            (
                scenario
                for scenario in scenarios
                if scenario["bet_line"] == "triple_barrel"
                and scenario["position"] == "IP"
                and scenario["texture_key"] == "any"
                and scenario["preflop_key"] == "any"
            ),
            None,
        )
        self.assertIsNotNone(double_barrel)
        if double_barrel is not None:
            metrics = {metric["bucket_key"]: metric for metric in double_barrel["metrics"]}
            bucket = metrics["pct_40_60"]
            self.assertEqual(bucket["events"], 2)
            self.assertEqual(bucket["fold_events"], 1)
            self.assertEqual(bucket["call_events"], 1)
            self.assertAlmostEqual(bucket["avg_ratio"], (0.55 + 0.6) / 2, places=6)
            self.assertAlmostEqual(bucket["avg_added_river_bb"], (4.0 + 4.5) / 2, places=6)

    def test_pot_contribution_payload(self) -> None:
        events = [
            {
                "bet_line": "float_river_stab",
                "position": "OOP",
                "player_count": 3,
                "ratio": 0.33,
                "bucket_key": "pct_25_40",
                "is_check": False,
                "is_all_in": False,
                "is_one_bb": False,
                "total_added_all_bb": 4.0,
                "hero_position": "SB",
                "river_texture_keys": ["three_tone"],
                "preflop_aggression_level": 0,
            },
            {
                "bet_line": "float_river_stab",
                "position": "OOP",
                "player_count": 3,
                "ratio": 0.28,
                "bucket_key": "pct_25_40",
                "is_check": False,
                "is_all_in": False,
                "is_one_bb": False,
                "total_added_all_bb": 3.5,
                "hero_position": "SB",
                "river_texture_keys": ["three_tone"],
                "preflop_aggression_level": 0,
            },
        ]

        payload = build_river_pot_contribution_payload(events)

        self.assertEqual(payload["version"], 1)
        scenarios = payload["scenarios"]
        self.assertTrue(scenarios)
        metrics = scenarios[0]["metrics"]
        pct_bucket = next(item for item in metrics if item["bucket_key"] == "pct_25_40")
        self.assertEqual(pct_bucket["events"], 2)
        self.assertAlmostEqual(pct_bucket["avg_added_bb"], (4.0 + 3.5) / 2, places=6)


if __name__ == "__main__":
    unittest.main()
