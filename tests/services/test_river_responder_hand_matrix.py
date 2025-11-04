"""Tests for river responder hand matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.river_responder_hand_matrix import _aggregate


class RiverResponderHandMatrixTests(unittest.TestCase):
    def test_aggregate_groups_responder_hands(self) -> None:
        events = [
            {
                "hero_position": "BTN",
                "bet_line": "triple_barrel",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.6,
                "bucket_key": "pct_40_60",
                "is_all_in": False,
                "is_one_bb": False,
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 1,
                "responses": [
                    {"response": "Call", "hand_primary": "Top Pair", "has_flush_draw": False, "has_oesd_dg": False},
                    {"response": "Raise", "hand_primary": "Flush", "has_flush_draw": False, "has_oesd_dg": False},
                ],
            },
            {
                "hero_position": "CO",
                "bet_line": "river_stab",
                "position": "IP",
                "player_count": 3,
                "ratio": 0.35,
                "bucket_key": "pct_25_40",
                "is_all_in": False,
                "is_one_bb": False,
                "river_texture_keys": ["two_tone"],
                "preflop_aggression_level": 0,
                "responses": [
                    {"response": "Call", "hand_primary": "Middle Pair", "has_flush_draw": True, "has_oesd_dg": False},
                ],
            },
        ]

        payload = _aggregate(events)

        self.assertEqual(payload["version"], 1)
        self.assertIn("scenarios", payload)
        textures = [option["key"] for option in payload["textures"]]
        self.assertIn("any", textures)
        response_types = [option["key"] for option in payload["response_types"]]
        self.assertIn("call", response_types)
        self.assertIn("raise", response_types)

        scenarios = payload["scenarios"]
        double_barrel_call = next(
            s
            for s in scenarios
            if s["bet_line"] == "triple_barrel"
            and s["response_type"] == "call"
            and s["texture_key"] == "any"
        )
        metrics = {metric["bucket_key"]: metric for metric in double_barrel_call["metrics"]}
        self.assertEqual(metrics["pct_40_60"]["categories"]["Top Pair"], 1)

        double_barrel_raise = next(
            s
            for s in scenarios
            if s["bet_line"] == "triple_barrel"
            and s["response_type"] == "raise"
        )
        metrics_raise = {metric["bucket_key"]: metric for metric in double_barrel_raise["metrics"]}
        self.assertEqual(metrics_raise["pct_40_60"]["categories"]["Flush"], 1)


if __name__ == "__main__":
    unittest.main()
