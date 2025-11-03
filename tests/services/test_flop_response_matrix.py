"""Tests for flop response matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.flop_response_matrix import build_flop_response_payload


class FlopResponseMatrixTests(unittest.TestCase):
    def test_aggregation_counts_events_and_outcomes(self) -> None:
        events = [
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.32,
                "responses": [{"response": "Fold"}],
                "total_added_flop_bb": 2.0,
                "total_added_all_bb": 4.0,
                "flop_texture_keys": ["rainbow", "connected"],
                "preflop_aggression_level": 0,
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.38,
                "responses": [{"response": "Call"}],
                "total_added_flop_bb": 2.5,
                "total_added_all_bb": 5.0,
                "flop_texture_keys": ["rainbow"],
                "preflop_aggression_level": 1,
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.35,
                "responses": [{"response": "Call"}, {"response": "Raise"}],
                "total_added_flop_bb": 3.0,
                "total_added_all_bb": 6.0,
                "flop_texture_keys": ["rainbow"],
                "preflop_aggression_level": 1,
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.45,
                "is_all_in": True,
                "responses": [{"response": "Fold"}],
                "total_added_flop_bb": 6.0,
                "total_added_all_bb": 12.0,
                "flop_texture_keys": ["monotone", "paired"],
                "preflop_aggression_level": 2,
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.12,
                "is_one_bb": True,
                "responses": [{"response": "Fold"}],
                "total_added_flop_bb": 1.0,
                "total_added_all_bb": 3.0,
                "flop_texture_keys": ["two_tone", "low"],
                "preflop_aggression_level": 0,
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 1.30,
                "responses": [{"response": "Call"}],
                "total_added_flop_bb": 8.0,
                "total_added_all_bb": 14.0,
                "flop_texture_keys": ["monotone", "ace_high"],
                "preflop_aggression_level": 3,
            },
            {
                "bet_type": "donk",
                "in_position": False,
                "player_count": 3,
                "ratio": 0.55,
                "responses": [{"response": "Call"}],
                "total_added_flop_bb": 4.0,
                "total_added_all_bb": 9.0,
                "flop_texture_keys": ["rainbow"],
                "preflop_aggression_level": 1,
            },
        ]

        payload = build_flop_response_payload(events)

        self.assertEqual(payload["version"], 8)
        # Ensure metadata is carried through
        bucket_keys = [bucket["key"] for bucket in payload["bucket_order"]]
        self.assertIn("pct_25_40", bucket_keys)
        self.assertIn("pct_100_plus", bucket_keys)
        self.assertIn("all_in", bucket_keys)
        self.assertIn("one_bb", bucket_keys)
        self.assertEqual(payload["player_counts"], [2, 3])
        texture_keys = [texture["key"] for texture in payload["textures"]]
        self.assertIn("any", texture_keys)
        self.assertIn("rainbow", texture_keys)
        preflop_keys = [option["key"] for option in payload["preflop_categories"]]
        self.assertIn("any", preflop_keys)
        self.assertIn("limped", preflop_keys)
        self.assertIn("single_raise", preflop_keys)
        self.assertIn("three_bet_plus", preflop_keys)

        scenarios = payload["scenarios"]
        self.assertTrue(scenarios)

        cbet_ip = next(
            (
                scenario
                for scenario in scenarios
                if scenario["bet_type"] == "cbet"
                and scenario["position"] == "IP"
                and scenario["texture_key"] == "any"
                and scenario["preflop_key"] == "any"
            ),
            None,
        )
        self.assertIsNotNone(cbet_ip)
        metrics = {metric["bucket_key"]: metric for metric in cbet_ip["metrics"]}

        pct_bucket = metrics["pct_25_40"]
        self.assertEqual(pct_bucket["events"], 3)
        self.assertEqual(pct_bucket["fold_events"], 1)
        self.assertEqual(pct_bucket["call_events"], 1)
        self.assertEqual(pct_bucket["raise_events"], 1)
        self.assertAlmostEqual(pct_bucket["avg_ratio"], (0.32 + 0.38 + 0.35) / 3, places=6)
        self.assertAlmostEqual(pct_bucket["avg_added_flop_bb"], (2.0 + 2.5 + 3.0) / 3, places=6)
        self.assertAlmostEqual(pct_bucket["avg_added_all_bb"], (4.0 + 5.0 + 6.0) / 3, places=6)
        self.assertAlmostEqual(
            pct_bucket["avg_added_all_bb"],
            (4.0 + 5.0 + 6.0) / 3,
            places=6,
        )
        expected_breakeven = sum(ratio / (1 + ratio) * 100 for ratio in (0.32, 0.38, 0.35)) / 3
        self.assertAlmostEqual(pct_bucket["avg_breakeven_pct"], expected_breakeven, places=6)

        medium_bucket = metrics["pct_40_60"]
        self.assertEqual(medium_bucket["events"], 1)
        self.assertEqual(medium_bucket["fold_events"], 1)

        all_in_bucket = metrics["all_in"]
        self.assertEqual(all_in_bucket["events"], 1)
        self.assertEqual(all_in_bucket["fold_events"], 1)

        one_bb_bucket = metrics["one_bb"]
        self.assertEqual(one_bb_bucket["events"], 1)

        large_bucket = metrics["pct_100_plus"]
        self.assertEqual(large_bucket["events"], 1)
        self.assertEqual(large_bucket["call_events"], 1)
        self.assertAlmostEqual(large_bucket["avg_added_flop_bb"], 8.0, places=6)
        self.assertAlmostEqual(large_bucket["avg_added_all_bb"], 14.0, places=6)
        self.assertAlmostEqual(large_bucket["avg_breakeven_pct"], 1.30 / (1 + 1.30) * 100, places=6)

        donk_scenario = next(
            (
                scenario
                for scenario in scenarios
                if scenario["bet_type"] == "donk"
                and scenario["position"] == "OOP"
                and scenario["texture_key"] == "any"
                and scenario["preflop_key"] == "any"
            ),
            None,
        )
        self.assertIsNotNone(donk_scenario)
        donk_metrics = {metric["bucket_key"]: metric for metric in donk_scenario["metrics"]}
        self.assertEqual(donk_metrics["pct_40_60"]["call_events"], 1)

        single_raise_scenario = next(
            (
                scenario
                for scenario in scenarios
                if scenario["bet_type"] == "cbet"
                and scenario["position"] == "IP"
                and scenario["texture_key"] == "any"
                and scenario["preflop_key"] == "single_raise"
            ),
            None,
        )
        self.assertIsNotNone(single_raise_scenario)
        if single_raise_scenario is not None:
            metrics = {metric["bucket_key"]: metric for metric in single_raise_scenario["metrics"]}
            self.assertEqual(metrics["pct_25_40"]["events"], 2)


if __name__ == "__main__":
    unittest.main()
