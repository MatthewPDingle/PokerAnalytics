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
                "responses": [
                    {
                        "response": "call",
                        "hand_primary": "Air",
                        "has_flush_draw": False,
                        "has_oesd_dg": False,
                    }
                ],
            },
        ]

        payload = _aggregate(events)

        self.assertEqual(payload["version"], 1)
        response_types = [option["key"] for option in payload["response_types"]]
        self.assertIn("call", response_types)
        self.assertIn("raise", response_types)

        scenarios = payload["scenarios"]
        call_scenario = next(
            (scenario for scenario in scenarios if scenario["response_type"] == "call"),
            None,
        )
        raise_scenario = next(
            (scenario for scenario in scenarios if scenario["response_type"] == "raise"),
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


if __name__ == "__main__":
    unittest.main()
