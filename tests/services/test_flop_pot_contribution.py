"""Tests for flop pot contribution aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.flop_response_matrix import build_flop_pot_contribution_payload


class FlopPotContributionTests(unittest.TestCase):
    def test_average_added_by_bucket(self) -> None:
        events = [
            {
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.32,
                "bucket_key": "pct_25_40",
                "total_added_all_bb": 2.5,
                "in_position": True,
            },
            {
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "ratio": 0.35,
                "bucket_key": "pct_25_40",
                "total_added_all_bb": 3.5,
                "in_position": True,
            },
            {
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "ratio": 1.40,
                "bucket_key": "pct_125_200",
                "total_added_all_bb": 8.0,
                "in_position": True,
            },
            {
                "hero_position": "SB",
                "bet_type": "donk",
                "position": "OOP",
                "player_count": 3,
                "ratio": 0.55,
                "bucket_key": "pct_40_60",
                "total_added_all_bb": 4.0,
                "in_position": False,
            },
        ]

        payload = build_flop_pot_contribution_payload(events)
        self.assertEqual(payload["version"], 4)
        scenarios = payload["scenarios"]
        self.assertTrue(scenarios)

        cbet = next(
            scenario
            for scenario in scenarios
            if scenario["hero_position"] == "BTN"
            and scenario["bet_type"] == "cbet"
            and scenario["position"] == "IP"
            and scenario["player_count"] == 2
        )
        cbet_metrics = {metric["bucket_key"]: metric for metric in cbet["metrics"]}
        self.assertAlmostEqual(cbet_metrics["pct_25_40"]["avg_added_bb"], (2.5 + 3.5) / 2, places=4)
        self.assertEqual(cbet_metrics["pct_25_40"]["events"], 2)
        self.assertAlmostEqual(cbet_metrics["pct_125_200"]["avg_added_bb"], 8.0, places=4)

        donk = next(
            scenario
            for scenario in scenarios
            if scenario["hero_position"] == "SB"
            and scenario["bet_type"] == "donk"
            and scenario["position"] == "OOP"
        )
        donk_metrics = {metric["bucket_key"]: metric for metric in donk["metrics"]}
        self.assertAlmostEqual(donk_metrics["pct_40_60"]["avg_added_bb"], 4.0, places=4)


if __name__ == "__main__":
    unittest.main()
