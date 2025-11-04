"""Tests for hero river hand matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.river_hand_matrix import _aggregate


class RiverHandMatrixTests(unittest.TestCase):
    def test_aggregate_counts_categories_and_buckets(self) -> None:
        events = [
            {
                "hand_primary": "Top Pair",
                "has_flush_draw": True,
                "has_oesd_dg": False,
                "hero_position": "BTN",
                "bet_line": "triple_barrel",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.55,
                "bucket_key": "pct_40_60",
                "is_all_in": False,
                "is_one_bb": False,
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 0,
            },
            {
                "hand_primary": "Trips/Set",
                "has_flush_draw": False,
                "has_oesd_dg": True,
                "hero_position": "BTN",
                "bet_line": "triple_barrel",
                "position": "IP",
                "player_count": 2,
                "ratio": 1.2,
                "bucket_key": "pct_100_plus",
                "is_all_in": False,
                "is_one_bb": False,
                "river_texture_keys": ["paired"],
                "preflop_aggression_level": 3,
            },
            {
                "hand_primary": "Air",
                "has_flush_draw": False,
                "has_oesd_dg": False,
                "hero_position": "CO",
                "bet_line": "river_stab",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.32,
                "bucket_key": "pct_25_40",
                "is_all_in": False,
                "is_one_bb": False,
                "river_texture_keys": ["two_tone", "high"],
                "preflop_aggression_level": 1,
            },
        ]

        payload = _aggregate(events)

        self.assertEqual(payload["version"], 1)
        self.assertIn("bucket_order", payload)
        self.assertIn("hand_types", payload)
        self.assertIn("scenarios", payload)
        texture_keys = [texture["key"] for texture in payload["textures"]]
        self.assertIn("any", texture_keys)
        preflop_keys = [option["key"] for option in payload["preflop_categories"]]
        self.assertIn("three_bet_plus", preflop_keys)

        scenarios = payload["scenarios"]
        self.assertTrue(scenarios)

        scenario = next(
            s
            for s in scenarios
            if s["hero_position"] == "BTN"
            and s["bet_line"] == "triple_barrel"
            and s["player_count"] == 2
            and s.get("texture_key") == "any"
            and s.get("preflop_key") == "any"
        )

        metrics = {metric["bucket_key"]: metric for metric in scenario["metrics"]}
        self.assertEqual(metrics["pct_40_60"]["categories"]["Top Pair"], 1)
        self.assertEqual(metrics["pct_40_60"]["categories"]["Flush Draw"], 1)

        three_bet_scenario = next(
            s
            for s in scenarios
            if s["hero_position"] == "BTN"
            and s["bet_line"] == "triple_barrel"
            and s["player_count"] == 2
            and s.get("preflop_key") == "three_bet_plus"
        )
        metrics_three_bet = {metric["bucket_key"]: metric for metric in three_bet_scenario["metrics"]}
        self.assertEqual(metrics_three_bet["pct_100_plus"]["events"], 1)


if __name__ == "__main__":
    unittest.main()
