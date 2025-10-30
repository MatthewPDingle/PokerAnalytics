"""Tests for hero flop hand matrix aggregation."""

from __future__ import annotations

import unittest

from poker_analytics.services.flop_hand_matrix import _aggregate


class FlopHandMatrixTests(unittest.TestCase):
    def test_aggregate_counts_categories_and_buckets(self) -> None:
        events = [
            {
                "hand_primary": "Top Pair",
                "has_flush_draw": True,
                "has_oesd_dg": False,
                "hero_position": "BTN",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.5,
                "bucket_key": "pct_40_60",
                "is_all_in": False,
                "is_one_bb": False,
            },
            {
                "hand_primary": "Trips/Set",
                "has_flush_draw": False,
                "has_oesd_dg": True,
                "hero_position": "BTN",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 1.35,
                "bucket_key": "pct_125_200",
                "is_all_in": False,
                "is_one_bb": False,
            },
            {
                "hand_primary": "Air",
                "has_flush_draw": False,
                "has_oesd_dg": False,
                "hero_position": "CO",
                "bet_type": "cbet",
                "in_position": True,
                "player_count": 2,
                "ratio": 0.3,
                "bucket_key": "pct_25_40",
                "is_all_in": False,
                "is_one_bb": False,
            },
        ]

        payload = _aggregate(events)

        self.assertEqual(payload["version"], 1)
        self.assertIn("bucket_order", payload)
        self.assertIn("hand_types", payload)
        self.assertIn("scenarios", payload)

        scenarios = payload["scenarios"]
        self.assertGreaterEqual(len(scenarios), 1)

        scenario = next(
            s for s in scenarios if s["hero_position"] == "BTN" and s["bet_type"] == "cbet" and s["player_count"] == 2
        )

        metrics = {metric["bucket_key"]: metric for metric in scenario["metrics"]}
        self.assertGreater(metrics["pct_40_60"]["events"], 0)
        self.assertEqual(metrics["pct_40_60"]["categories"]["Top Pair"], 1)
        self.assertEqual(metrics["pct_40_60"]["categories"]["Flush Draw"], 1)

        self.assertEqual(metrics["pct_125_200"]["events"], 1)
        self.assertEqual(metrics["pct_125_plus"]["events"], 1)
        self.assertEqual(metrics["pct_125_plus"]["categories"]["Trips/Set"], 1)
        self.assertEqual(metrics["pct_125_plus"]["categories"]["OESD/DG"], 1)


if __name__ == "__main__":
    unittest.main()
