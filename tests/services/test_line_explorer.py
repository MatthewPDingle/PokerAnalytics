"""Tests for line explorer aggregations."""

from __future__ import annotations

import unittest

from poker_analytics.services.line_explorer import CURRENT_VERSION, build_line_explorer_payload
from poker_analytics.services.line_responder_hand_matrix import (
    CURRENT_VERSION as RESPONDER_VERSION,
    build_line_responder_hand_payload,
)


class LineExplorerTests(unittest.TestCase):
    def test_build_line_explorer_payload(self) -> None:
        events = [
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_40_60",
                "turn_ratio": 0.55,
                "bet_amount_bb": 5.5,
                "outcome": "fold",
            },
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_40_60",
                "turn_ratio": 0.6,
                "bet_amount_bb": 6.0,
                "outcome": "call",
            },
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_0_25",
                "turn_ratio": 0.1,
                "bet_amount_bb": 1.0,
                "outcome": "call",
                "is_one_bb": True,
            },
            {
                "line_key": "c_turn_b",
                "response_type": "call",
                "hero_position": "CO",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 3,
                "turn_bucket_key": "pct_25_40",
                "turn_ratio": 0.3,
                "bet_amount_bb": 3.0,
                "outcome": "fold",
            },
            {
                "line_key": "c_turn_b",
                "response_type": "call",
                "hero_position": "CO",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 3,
                "turn_bucket_key": "pct_300_plus",
                "turn_ratio": 3.5,
                "bet_amount_bb": 35.0,
                "outcome": "call",
                "is_all_in": True,
            },
        ]

        payload = build_line_explorer_payload(events)

        self.assertEqual(payload["version"], CURRENT_VERSION)
        self.assertEqual(payload["line_definitions"], [
            {"key": "xc_turn_b", "label": "Flop Check-Call → Turn Bet"},
            {"key": "c_turn_b", "label": "Flop Call → Turn Bet"},
        ])
        self.assertEqual(len(payload["scenarios"]), 2)
        metrics = next(s for s in payload["scenarios"] if s["line_key"] == "xc_turn_b")["metrics"]
        pct_bucket = next(item for item in metrics if item["bucket_key"] == "pct_40_60")
        self.assertEqual(pct_bucket["events"], 2)
        self.assertEqual(pct_bucket["fold_events"], 1)
        self.assertEqual(pct_bucket["call_events"], 1)
        self.assertAlmostEqual(pct_bucket["avg_ratio"], (0.55 + 0.6) / 2)
        one_bb_bucket = next(item for item in metrics if item["bucket_key"] == "one_bb")
        self.assertEqual(one_bb_bucket["events"], 1)

        other_metrics = next(s for s in payload["scenarios"] if s["line_key"] == "c_turn_b")["metrics"]
        all_in_bucket = next(item for item in other_metrics if item["bucket_key"] == "all_in")
        self.assertEqual(all_in_bucket["events"], 1)

    def test_build_line_responder_hand_payload(self) -> None:
        events = [
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_40_60",
                "hand_primary": "Top Pair",
                "has_flush_draw": False,
                "has_oesd_dg": False,
            },
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_40_60",
                "hand_primary": "Flush Draw",
                "has_flush_draw": True,
                "has_oesd_dg": False,
            },
            {
                "line_key": "xc_turn_b",
                "response_type": "call",
                "hero_position": "BTN",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 2,
                "turn_bucket_key": "pct_0_25",
                "turn_ratio": 0.1,
                "bet_amount_bb": 1.0,
                "hand_primary": "Top Pair",
                "has_flush_draw": False,
                "has_oesd_dg": False,
                "is_one_bb": True,
            },
            {
                "line_key": "c_turn_b",
                "response_type": "call",
                "hero_position": "CO",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 3,
                "turn_bucket_key": "pct_25_40",
                "hand_primary": "Top Pair",
                "has_flush_draw": False,
                "has_oesd_dg": False,
            },
            {
                "line_key": "c_turn_b",
                "response_type": "call",
                "hero_position": "CO",
                "bet_type": "cbet",
                "position": "IP",
                "player_count": 3,
                "turn_bucket_key": "pct_300_plus",
                "turn_ratio": 3.5,
                "bet_amount_bb": 35.0,
                "hand_primary": "Top Pair",
                "has_flush_draw": False,
                "has_oesd_dg": False,
                "is_all_in": True,
            },
        ]

        payload = build_line_responder_hand_payload(events)

        self.assertEqual(payload["version"], RESPONDER_VERSION)
        self.assertEqual(payload["line_definitions"], [
            {"key": "xc_turn_b", "label": "Flop Check-Call → Turn Bet"},
            {"key": "c_turn_b", "label": "Flop Call → Turn Bet"},
        ])
        scenario = next(s for s in payload["scenarios"] if s["line_key"] == "xc_turn_b")
        metrics = {metric["bucket_key"]: metric for metric in scenario["metrics"]}
        bucket = metrics["pct_40_60"]
        self.assertEqual(bucket["events"], 2)
        self.assertEqual(bucket["categories"]["Top Pair"], 1)
        self.assertEqual(bucket["categories"]["Flush Draw"], 2)
        one_bb = metrics["one_bb"]
        self.assertEqual(one_bb["events"], 1)
        all_in = next(metric for metric in payload["scenarios"] if metric["line_key"] == "c_turn_b")["metrics"]
        all_in_bucket = next(item for item in all_in if item["bucket_key"] == "all_in")
        self.assertEqual(all_in_bucket["events"], 1)


if __name__ == "__main__":
    unittest.main()
