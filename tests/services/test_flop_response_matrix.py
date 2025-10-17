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
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.38,
                "responses": [{"response": "Call"}],
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.35,
                "responses": [{"response": "Call"}, {"response": "Raise"}],
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.45,
                "is_all_in": True,
                "responses": [{"response": "Fold"}],
            },
            {
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.12,
                "is_one_bb": True,
                "responses": [{"response": "Fold"}],
            },
            {
                "bet_type": "donk",
                "in_position": False,
                "player_count": 3,
                "ratio": 0.55,
                "responses": [{"response": "Call"}],
            },
        ]

        payload = build_flop_response_payload(events)

        # Ensure metadata is carried through
        bucket_keys = [bucket["key"] for bucket in payload["bucket_order"]]
        self.assertIn("pct_25_40", bucket_keys)
        self.assertIn("all_in", bucket_keys)
        self.assertIn("one_bb", bucket_keys)
        self.assertEqual(payload["player_counts"], [2, 3])

        scenarios = payload["scenarios"]
        self.assertTrue(scenarios)

        cbet_ip = next(
            (scenario for scenario in scenarios if scenario["bet_type"] == "cbet" and scenario["position"] == "IP"),
            None,
        )
        self.assertIsNotNone(cbet_ip)
        metrics = {metric["bucket_key"]: metric for metric in cbet_ip["metrics"]}

        pct_bucket = metrics["pct_25_40"]
        self.assertEqual(pct_bucket["events"], 3)
        self.assertEqual(pct_bucket["fold_events"], 1)
        self.assertEqual(pct_bucket["call_events"], 1)
        self.assertEqual(pct_bucket["raise_events"], 1)

        all_in_bucket = metrics["all_in"]
        self.assertEqual(all_in_bucket["events"], 1)
        self.assertEqual(all_in_bucket["fold_events"], 1)

        one_bb_bucket = metrics["one_bb"]
        self.assertEqual(one_bb_bucket["events"], 1)

        donk_scenario = next(
            (scenario for scenario in scenarios if scenario["bet_type"] == "donk" and scenario["position"] == "OOP"),
            None,
        )
        self.assertIsNotNone(donk_scenario)
        donk_metrics = {metric["bucket_key"]: metric for metric in donk_scenario["metrics"]}
        self.assertEqual(donk_metrics["pct_40_60"]["call_events"], 1)


if __name__ == "__main__":
    unittest.main()
