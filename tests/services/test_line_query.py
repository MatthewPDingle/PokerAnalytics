import os
import tempfile
import unittest
from typing import Any, Dict, List

from poker_analytics.services.line_query import query_line


def _sample_events() -> List[Dict[str, Any]]:
    return [
        {
            "line_key": "xc_turn_b",
            "response_type": "call",
            "bet_type": "cbet",
            "position": "OOP",
            "player_count": 2,
            "hero_position": "SB",
            "turn_bucket_key": "pct_40_60",
            "turn_ratio": 0.5,
            "outcome": "call",
            "bet_amount_bb": 5.0,
            "hand_primary": "Top Pair",
            "has_flush_draw": False,
            "has_oesd_dg": True,
            "total_added_flop_bb": 1.2,
            "total_added_all_bb": 3.8,
            "total_share_all": 1.6,
            "flop_texture_keys": ["connected", "low"],
            "bettor_is_hero": False,
            "responder_is_hero": False,
        },
        {
            "line_key": "xc_turn_b",
            "response_type": "call",
            "bet_type": "cbet",
            "position": "OOP",
            "player_count": 2,
            "hero_position": "SB",
            "turn_bucket_key": "pct_40_60",
            "turn_ratio": 0.55,
            "outcome": "fold",
            "bet_amount_bb": 5.5,
            "hand_primary": "Air",
            "has_flush_draw": True,
            "has_oesd_dg": False,
            "total_added_flop_bb": 1.0,
            "total_added_all_bb": 2.0,
            "total_share_all": 1.2,
            "flop_texture_keys": ["connected"],
            "bettor_is_hero": False,
            "responder_is_hero": False,
        },
        {
            "line_key": "c_turn_b",
            "response_type": "raise",
            "bet_type": "donk",
            "position": "IP",
            "player_count": 3,
            "hero_position": "BTN",
            "turn_bucket_key": "pct_60_80",
            "turn_ratio": 0.7,
            "outcome": "raise",
            "bet_amount_bb": 8.0,
            "hand_primary": "Trips/Set",
            "has_flush_draw": False,
            "has_oesd_dg": False,
            "total_added_flop_bb": 2.0,
            "total_added_all_bb": 6.0,
            "total_share_all": 2.4,
            "flop_texture_keys": ["paired"],
            "bettor_is_hero": False,
            "responder_is_hero": False,
        },
    ]


class LineQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.original_cache_dir = os.getenv("POKER_ANALYTICS_CACHE_DIR")
        os.environ["POKER_ANALYTICS_CACHE_DIR"] = self.tmp_dir.name

    def tearDown(self) -> None:
        if self.original_cache_dir is None:
            os.environ.pop("POKER_ANALYTICS_CACHE_DIR", None)
        else:
            os.environ["POKER_ANALYTICS_CACHE_DIR"] = self.original_cache_dir

    def test_query_line_filters_response_type_and_bucket(self) -> None:
        payload = {
            "steps": [
                {"street": "flop", "actor": "responder", "action": "call"},
                {"street": "turn", "actor": "bettor", "action": "bet", "sizing": {"bucket_keys": ["pct_40_60"]}},
            ],
            "filters": {"excludeHero": True},
        }

        response = query_line(payload, events=_sample_events())

        self.assertGreaterEqual(response["version"], 2)
        metrics = {row["bucket_key"]: row for row in response["response_metrics"]}
        bucket = metrics["pct_40_60"]
        self.assertEqual(bucket["events"], 2)
        self.assertEqual(bucket["call_events"], 1)
        self.assertEqual(bucket["fold_events"], 1)
        self.assertEqual(bucket["continue_events"], 1)
        self.assertEqual(response["context"]["total_events"], 2)
        hand_metrics = {row["bucket_key"]: row for row in response["hand_metrics"]}
        hand_bucket = hand_metrics["pct_40_60"]
        self.assertEqual(hand_bucket["categories"]["Top Pair"], 1)
        self.assertEqual(hand_bucket["categories"]["Air"], 1)
        self.assertEqual(hand_bucket["categories"]["Flush Draw"], 1)
        self.assertIn("request_filters", response)
        self.assertTrue(response["request_filters"].get("excludeHero"))
        self.assertIn("descriptor_fingerprint", response)
        self.assertIn("exclude_hero", response["context"]["applied_filters"])

    def test_query_line_filters_raise_events(self) -> None:
        payload = {
            "steps": [
                {"street": "flop", "actor": "responder", "action": "raise"},
                {"street": "flop", "actor": "bettor", "action": "donk"},
                {"street": "turn", "actor": "bettor", "action": "bet"},
            ]
        }

        response = query_line(payload, events=_sample_events())

        self.assertEqual(response["context"]["total_events"], 1)
        metrics = {row["bucket_key"]: row for row in response["response_metrics"]}
        self.assertEqual(metrics["pct_60_80"]["events"], 1)
        self.assertEqual(metrics["pct_60_80"]["raise_events"], 1)

    def test_query_line_filters_texture_keys(self) -> None:
        payload = {
            "steps": [
                {"street": "flop", "actor": "responder", "action": "call", "qualifiers": ["texture_connected"]},
                {"street": "turn", "actor": "bettor", "action": "bet"},
            ]
        }

        response = query_line(payload, events=_sample_events())

        self.assertEqual(response["context"]["total_events"], 2)
        applied = response["context"]["applied_filters"]
        self.assertIn("texture_keys", applied)
        self.assertEqual(applied["texture_keys"], ["connected"])
        metrics = {row["bucket_key"]: row for row in response["response_metrics"]}
        self.assertEqual(metrics["pct_60_80"]["events"], 0)


if __name__ == "__main__":
    unittest.main()
