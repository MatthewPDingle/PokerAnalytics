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
            "player_count": 3,
            "hero_position": "SB",
            "turn_bucket_key": "pct_40_60",
            "bucket_key": "pct_40_60",
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
            "preflop_bucket_key": "pct_100_plus",
            "players_dealt": 6,
            "players_remaining": 3,
            "relative_position": "early",
            "actor_seat": "SB",
            "is_check": False,
            "is_all_in": False,
            "is_one_bb": False,
            "behind_responses": [
                {
                    "seat_label": "BTN",
                    "relative_position": "late",
                    "response_type": "call",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "Middle Pair",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": True,
                },
                {
                    "seat_label": "BB",
                    "relative_position": "late",
                    "response_type": "fold",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": False,
                },
            ],
        },
        {
            "line_key": "xc_turn_b",
            "response_type": "call",
            "bet_type": "cbet",
            "position": "OOP",
            "player_count": 3,
            "hero_position": "SB",
            "turn_bucket_key": "pct_40_60",
            "bucket_key": "pct_40_60",
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
            "preflop_bucket_key": "pct_100_plus",
            "players_dealt": 6,
            "players_remaining": 3,
            "relative_position": "early",
            "actor_seat": "SB",
            "is_check": False,
            "is_all_in": False,
            "is_one_bb": False,
            "behind_responses": [
                {
                    "seat_label": "BTN",
                    "relative_position": "late",
                    "response_type": "raise",
                    "bucket_key": "pct_60_80",
                    "bucket_keys": ["pct_60_80"],
                    "ratio": 0.62,
                    "bet_amount_bb": 6.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "Overpair",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": True,
                },
                {
                    "seat_label": "CO",
                    "relative_position": "middle",
                    "response_type": "call",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": False,
                },
            ],
        },
        {
            "line_key": "c_turn_b",
            "response_type": "raise",
            "bet_type": "donk",
            "position": "IP",
            "player_count": 4,
            "hero_position": "BTN",
            "turn_bucket_key": "pct_60_80",
            "bucket_key": "pct_60_80",
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
            "preflop_bucket_key": "pct_100_plus",
            "players_dealt": 6,
            "players_remaining": 4,
            "relative_position": "middle",
            "actor_seat": "BTN",
            "is_check": False,
            "is_all_in": False,
            "is_one_bb": False,
            "behind_responses": [
                {
                    "seat_label": "CO",
                    "relative_position": "middle",
                    "response_type": "fold",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": False,
                },
                {
                    "seat_label": "HJ",
                    "relative_position": "early",
                    "response_type": "raise",
                    "bucket_key": "pct_80_100",
                    "bucket_keys": ["pct_80_100"],
                    "ratio": 0.85,
                    "bet_amount_bb": 9.5,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "Flush",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": True,
                },
            ],
        },
        {
            "line_key": "xc_turn_b",
            "response_type": "call",
            "bet_type": "cbet",
            "position": "OOP",
            "player_count": 2,
            "hero_position": "SB",
            "turn_bucket_key": "pct_0_25",
            "bucket_key": "pct_0_25",
            "turn_ratio": 0.1,
            "outcome": "call",
            "bet_amount_bb": 1.0,
            "hand_primary": "Second Pair",
            "has_flush_draw": False,
            "has_oesd_dg": False,
            "total_added_flop_bb": 0.6,
            "total_added_all_bb": 1.6,
            "total_share_all": 0.8,
            "flop_texture_keys": ["rainbow"],
            "bettor_is_hero": False,
            "responder_is_hero": False,
            "is_one_bb": True,
            "preflop_bucket_key": "pct_100_plus",
            "players_dealt": 6,
            "players_remaining": 2,
            "relative_position": "early",
            "actor_seat": "SB",
            "is_check": False,
            "is_all_in": False,
            "behind_responses": [
                {
                    "seat_label": "BB",
                    "relative_position": "late",
                    "response_type": "bet",
                    "bucket_key": "pct_25_40",
                    "bucket_keys": ["pct_25_40"],
                    "ratio": 0.3,
                    "bet_amount_bb": 2.5,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "Air",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": True,
                }
            ],
        },
        {
            "line_key": "c_turn_b",
            "response_type": "call",
            "bet_type": "donk",
            "position": "IP",
            "player_count": 3,
            "hero_position": "BTN",
            "turn_bucket_key": "pct_100_plus",
            "bucket_key": "pct_100_plus",
            "turn_ratio": 3.2,
            "outcome": "call",
            "bet_amount_bb": 40.0,
            "hand_primary": "Overpair",
            "has_flush_draw": False,
            "has_oesd_dg": False,
            "total_added_flop_bb": 3.0,
            "total_added_all_bb": 9.0,
            "total_share_all": 3.5,
            "flop_texture_keys": ["paired"],
            "bettor_is_hero": False,
            "responder_is_hero": False,
            "is_all_in": True,
            "preflop_bucket_key": "pct_25_40",
            "players_dealt": 6,
            "players_remaining": 3,
            "relative_position": "late",
            "actor_seat": "BTN",
            "is_check": False,
            "behind_responses": [
                {
                    "seat_label": "SB",
                    "relative_position": "early",
                    "response_type": "fold",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": False,
                },
                {
                    "seat_label": "BB",
                    "relative_position": "middle",
                    "response_type": "call",
                    "bucket_key": None,
                    "bucket_keys": [],
                    "ratio": 0.0,
                    "bet_amount_bb": 0.0,
                    "is_all_in": False,
                    "is_one_bb": False,
                    "hand_primary": "Two Pair",
                    "has_flush_draw": False,
                    "has_oesd_dg": False,
                    "hole_cards_known": True,
                },
            ],
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

        self.assertGreaterEqual(response["version"], 5)
        summaries = {row["action_key"]: row for row in response["action_summaries"]}
        bucket = summaries["pct_40_60"]
        self.assertEqual(bucket["events"], 2)
        self.assertEqual(bucket["call_events"], 1)
        self.assertEqual(bucket["fold_events"], 1)
        self.assertEqual(bucket["continue_events"], 1)
        self.assertEqual(response["context"]["total_events"], 2)
        hand_mix = bucket["hand_categories"]
        self.assertEqual(hand_mix["Top Pair"], 1)
        self.assertEqual(hand_mix["Air"], 1)
        self.assertEqual(hand_mix["Flush Draw"], 1)

        hero_actions = bucket["hero_actions"]
        self.assertEqual(hero_actions["bet_any"], 2)
        self.assertEqual(hero_actions["pct_40_60"], 2)
        self.assertEqual(hero_actions.get("check", 0), 0)

        responder_summary = bucket["responder_summary"]
        self.assertEqual(responder_summary["total_responses"], 4)
        self.assertEqual(responder_summary["hand_categories"]["Middle Pair"], 1)
        self.assertEqual(responder_summary["hand_categories"]["Overpair"], 1)
        self.assertEqual(responder_summary["hand_categories"]["Unknown"], 2)
        seating = {seat["seat_label"]: seat for seat in responder_summary["seats"]}
        self.assertIn("BTN", seating)
        self.assertEqual(seating["BTN"]["responses"], 2)
        self.assertEqual(seating["BTN"]["action_counts"]["call"], 1)
        self.assertEqual(seating["BTN"]["action_counts"]["raise"], 1)

        totals = response["totals"]
        self.assertGreater(totals["hero_actions"]["bet_any"], 0)

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
        summaries = {row["action_key"]: row for row in response["action_summaries"]}
        self.assertEqual(summaries["pct_60_80"]["events"], 1)
        self.assertEqual(summaries["pct_60_80"]["raise_events"], 1)

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
        summaries = {row["action_key"]: row for row in response["action_summaries"]}
        self.assertEqual(summaries["pct_60_80"]["events"], 0)

    def test_query_line_counts_special_buckets(self) -> None:
        payload = {
            "steps": [
                {"street": "flop", "actor": "responder", "action": "call"},
                {"street": "turn", "actor": "bettor", "action": "bet"},
            ]
        }

        response = query_line(payload, events=_sample_events())

        summaries = {row["action_key"]: row for row in response["action_summaries"]}
        self.assertEqual(summaries["pct_0_25"]["events"], 1)
        self.assertEqual(summaries["one_bb"]["events"], 1)
        self.assertEqual(summaries["pct_100_plus"]["events"], 1)
        self.assertEqual(summaries["all_in"]["events"], 1)

        filtered = query_line(
            {
                "steps": [
                    {"street": "flop", "actor": "responder", "action": "call"},
                    {"street": "turn", "actor": "bettor", "action": "bet"},
                ],
                "filters": {"preflopBucketKeys": ["pct_100_plus"]},
            },
            events=_sample_events(),
        )

        self.assertEqual(filtered["context"]["total_events"], 3)
        filtered_summaries = {row["action_key"]: row for row in filtered["action_summaries"]}
        self.assertEqual(filtered_summaries["pct_100_plus"]["events"], 0)
        self.assertEqual(filtered_summaries["all_in"]["events"], 0)


if __name__ == "__main__":
    unittest.main()
