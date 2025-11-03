"""Tests for responder hand matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.flop_responder_hand_matrix import _aggregate


class FlopResponderHandMatrixTests(unittest.TestCase):
    def test_aggregate_groups_by_response_type(self) -> None:
        events = [
            {
                "hero_position": "BTN",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.55,
                "bucket_key": "pct_40_60",
                "is_all_in": False,
                "is_one_bb": False,
                "flop_texture_keys": ["rainbow"],
                "preflop_aggression_level": 0,
                "responses": [
                    {
                        "response": "call",
                        "hand_primary": "Top Pair",
                        "has_flush_draw": False,
                        "has_oesd_dg": False,
                    },
                    {
                        "response": "call",
                        "hand_primary": "Flush Draw",
                        "has_flush_draw": True,
                        "has_oesd_dg": False,
                    },
                    {
                        "response": "raise",
                        "hand_primary": "Overpair",
                        "has_flush_draw": False,
                        "has_oesd_dg": False,
                    },
                ],
            },
            {
                "hero_position": "BTN",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.25,
                "bucket_key": "pct_25_40",
                "is_all_in": False,
                "is_one_bb": False,
                "flop_texture_keys": ["two_tone"],
                "preflop_aggression_level": 1,
                "responses": [
                    {
                        "response": "call",
                        "hand_primary": "Air",
                        "has_flush_draw": False,
                        "has_oesd_dg": False,
                    }
                ],
            },
            {
                "hero_position": "CO",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 1.25,
                "bucket_key": "pct_100_plus",
                "is_all_in": False,
                "is_one_bb": False,
                "flop_texture_keys": ["monotone"],
                "preflop_aggression_level": 3,
                "responses": [
                    {
                        "response": "raise",
                        "hand_primary": "Overpair",
                        "has_flush_draw": False,
                        "has_oesd_dg": False,
                    }
                ],
            },
        ]

        payload = _aggregate(events)

        self.assertEqual(payload["version"], 5)
        response_types = [option["key"] for option in payload["response_types"]]
        self.assertIn("call", response_types)
        self.assertIn("raise", response_types)
        texture_keys = [texture["key"] for texture in payload["textures"]]
        self.assertIn("any", texture_keys)
        preflop_keys = [option["key"] for option in payload["preflop_categories"]]
        self.assertIn("any", preflop_keys)
        self.assertIn("limped", preflop_keys)
        self.assertIn("single_raise", preflop_keys)
        self.assertIn("three_bet_plus", preflop_keys)

        scenarios = payload["scenarios"]
        call_scenario = next(
            (
                scenario
                for scenario in scenarios
                if scenario["response_type"] == "call"
                and scenario.get("texture_key") == "any"
                and scenario.get("preflop_key") == "any"
            ),
            None,
        )
        raise_scenario = next(
            (
                scenario
                for scenario in scenarios
                if scenario["hero_position"] == "BTN"
                and scenario["response_type"] == "raise"
                and scenario.get("texture_key") == "any"
                and scenario.get("preflop_key") == "any"
            ),
            None,
        )

        self.assertIsNotNone(call_scenario)
        self.assertIsNotNone(raise_scenario)

        if call_scenario is not None:
            metrics = {metric["bucket_key"]: metric for metric in call_scenario["metrics"]}
            self.assertEqual(metrics["pct_40_60"]["events"], 2)
            self.assertEqual(metrics["pct_40_60"]["categories"]["Top Pair"], 1)
            self.assertGreaterEqual(metrics["pct_40_60"]["categories"]["Flush Draw"], 1)
            self.assertEqual(metrics["pct_25_40"]["events"], 1)

        if raise_scenario is not None:
            metrics = {metric["bucket_key"]: metric for metric in raise_scenario["metrics"]}
            self.assertEqual(metrics["pct_40_60"]["events"], 1)
            self.assertEqual(metrics["pct_40_60"]["categories"]["Overpair"], 1)

        single_raise_call = next(
            (
                scenario
                for scenario in scenarios
                if scenario["response_type"] == "call"
                and scenario.get("texture_key") == "any"
                and scenario.get("preflop_key") == "single_raise"
            ),
            None,
        )
        self.assertIsNotNone(single_raise_call)
        if single_raise_call is not None:
            metrics = {metric["bucket_key"]: metric for metric in single_raise_call["metrics"]}
            self.assertEqual(metrics["pct_25_40"]["events"], 1)

        three_bet_raise = next(
            (
                scenario
                for scenario in scenarios
                if scenario["response_type"] == "raise"
                and scenario.get("texture_key") == "any"
                and scenario.get("preflop_key") == "three_bet_plus"
            ),
            None,
        )
        self.assertIsNotNone(three_bet_raise)
        if three_bet_raise is not None:
            metrics = {metric["bucket_key"]: metric for metric in three_bet_raise["metrics"]}
            self.assertEqual(metrics["pct_100_plus"]["events"], 1)


if __name__ == "__main__":
    unittest.main()
