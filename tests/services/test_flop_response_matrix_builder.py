"""Tests for flop response matrix builder helpers."""

from __future__ import annotations

import textwrap
import unittest

from poker_analytics.data.stakes import StakePolicy
from poker_analytics.services.flop_response_matrix_builder import _events_from_hand_history

STAKE_POLICY = StakePolicy(allowed_big_blinds=(0.10,))


def _wrap_xml(body: str, hero: str = "Hero") -> str:
    return textwrap.dedent(
        f"""
        <session sessioncode="0">
          <game gamecode="1">
            <general>
              <gametype>Holdem NL $0.05/$0.10</gametype>
              <nickname>{hero}</nickname>
              <players>
                <player seat="1" name="Hero" chips="10" dealer="1" />
                <player seat="3" name="Villain" chips="10" dealer="0" />
              </players>
            </general>
{body}
          </game>
        </session>
        """
    ).strip()


class FlopResponseMatrixBuilderTests(unittest.TestCase):
    def test_cbet_event(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="1">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Observer</nickname>
                  <players>
                    <player seat="1" name="Observer" chips="10" dealer="1" />
                    <player seat="3" name="Villain" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Observer" type="1" sum="0.05" cards="" />
                  <action no="1" player="Villain" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Villain" type="23" sum="0.30" cards="" />
                  <action no="3" player="Observer" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <action no="4" player="Villain" type="4" sum="0" cards="" />
                  <action no="5" player="Villain" type="5" sum="0.20" cards="" />
                  <action no="6" player="Observer" type="0" sum="0" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "cbet")
        self.assertFalse(event["in_position"])
        self.assertEqual(event["player_count"], 2)
        self.assertEqual(event["villain_outcome"], "fold")
        self.assertAlmostEqual(event["ratio"], 0.20 / 0.75, places=6)
        self.assertEqual(event["bucket_key"], "pct_25_40")
        self.assertFalse(event["bettor_is_hero"])
        self.assertGreater(event["total_added_flop_bb"], 0)
        self.assertAlmostEqual(event["total_added_all_bb"], event["total_added_flop_bb"], places=6)
        self.assertIn("responses", event)
        self.assertIsInstance(event["responses"], list)

    def test_donk_event(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="2">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Observer</nickname>
                  <players>
                    <player seat="1" name="Observer" chips="10" dealer="0" />
                    <player seat="3" name="Aggressor" chips="10" dealer="1" />
                    <player seat="5" name="BigBlind" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Observer" type="1" sum="0.05" cards="" />
                  <action no="1" player="BigBlind" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Observer" type="3" sum="0.05" cards="" />
                  <action no="3" player="Aggressor" type="23" sum="0.30" cards="" />
                  <action no="4" player="BigBlind" type="0" sum="0" cards="" />
                  <action no="5" player="Observer" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <action no="6" player="BigBlind" type="5" sum="0.20" cards="" />
                  <action no="7" player="Aggressor" type="3" sum="0.20" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "donk")
        self.assertFalse(event["in_position"])
        self.assertEqual(event["player_count"], 2)
        self.assertEqual(event["villain_outcome"], "call")
        self.assertFalse(event["bettor_is_hero"])
        self.assertGreater(event["total_added_flop_bb"], 0)
        self.assertAlmostEqual(event["total_added_all_bb"], event["total_added_flop_bb"], places=6)
        self.assertIn("responses", event)

    def test_stab_event(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="3">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Observer</nickname>
                  <players>
                    <player seat="1" name="Observer" chips="10" dealer="0" />
                    <player seat="3" name="Aggressor" chips="10" dealer="0" />
                    <player seat="5" name="Cutoff" chips="10" dealer="1" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Observer" type="1" sum="0.05" cards="" />
                  <action no="1" player="Aggressor" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Aggressor" type="23" sum="0.30" cards="" />
                  <action no="3" player="Cutoff" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <action no="4" player="Aggressor" type="4" sum="0" cards="" />
                  <action no="5" player="Cutoff" type="5" sum="0.20" cards="" />
                  <action no="6" player="Observer" type="0" sum="0" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "donk")
        self.assertTrue(event["in_position"])
        self.assertEqual(event["villain_outcome"], "fold")
        self.assertFalse(event["bettor_is_hero"])
        self.assertGreater(event["total_added_flop_bb"], 0)
        self.assertAlmostEqual(event["total_added_all_bb"], event["total_added_flop_bb"], places=6)
        self.assertIn("responses", event)

    def test_non_hero_bet_included(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="4">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Hero</nickname>
                  <players>
                    <player seat="1" name="Hero" chips="10" dealer="1" />
                    <player seat="3" name="Villain" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Hero" type="1" sum="0.05" cards="" />
                  <action no="1" player="Villain" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Hero" type="23" sum="0.30" cards="" />
                  <action no="3" player="Villain" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <action no="4" player="Hero" type="4" sum="0" cards="" />
                  <action no="5" player="Villain" type="5" sum="0.20" cards="" />
                  <action no="6" player="Hero" type="0" sum="0" cards="" />
                </round>
                <round no="3">
                  <action no="7" player="Villain" type="5" sum="0.40" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(len(events), 1)

    def test_responses_capture_call_and_raise(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="10">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Hero</nickname>
                  <players>
                    <player seat="1" name="Hero" chips="10" dealer="1" />
                    <player seat="3" name="Bettor" chips="10" dealer="0" />
                    <player seat="5" name="Caller" chips="10" dealer="0" />
                    <player seat="7" name="Raiser" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Hero" type="1" sum="0.05" cards="" />
                  <action no="1" player="Bettor" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <cards player="Hero" cards="C5 D5" />
                  <cards player="Bettor" cards="HA DA" />
                  <cards player="Caller" cards="HK DK" />
                  <cards player="Raiser" cards="HQ DQ" />
                  <action no="2" player="Caller" type="23" sum="0.30" cards="" />
                  <action no="3" player="Raiser" type="23" sum="0.60" cards="" />
                  <action no="4" player="Hero" type="0" sum="0" cards="" />
                  <action no="5" player="Bettor" type="3" sum="0.50" cards="" />
                  <action no="6" player="Caller" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <cards type="flop" cards="C2 D7 H9" />
                  <action no="7" player="Bettor" type="5" sum="0.90" cards="" />
                  <action no="8" player="Caller" type="3" sum="0.90" cards="" />
                  <action no="9" player="Raiser" type="23" sum="2.70" cards="" />
                  <action no="10" player="Bettor" type="3" sum="1.80" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(len(events), 1)
        responses = events[0].get("responses")
        self.assertIsInstance(responses, list)
        call_entry = next((entry for entry in responses if entry.get("response") == "call"), None)
        raise_entry = next((entry for entry in responses if entry.get("response") == "raise"), None)
        self.assertIsNotNone(call_entry)
        self.assertIsNotNone(raise_entry)
        if call_entry is not None:
            self.assertEqual(call_entry.get("hand_primary"), "Overpair")
        if raise_entry is not None:
            self.assertEqual(raise_entry.get("hand_primary"), "Overpair")
        event = events[0]
        self.assertEqual(event["bettor"], "Bettor")
        self.assertEqual(event["bet_type"], "donk")
        self.assertFalse(event["in_position"])
        self.assertFalse(event["bettor_is_hero"])
        self.assertGreaterEqual(event["total_added_all_bb"], event.get("total_added_flop_bb", 0))

    def test_hero_bet_excluded(self) -> None:
        xml = _wrap_xml(
            """
            <round no="0">
              <action no="0" player="Hero" type="1" sum="0.05" cards="" />
              <action no="1" player="Villain" type="2" sum="0.10" cards="" />
            </round>
            <round no="1">
              <action no="2" player="Hero" type="23" sum="0.30" cards="" />
              <action no="3" player="Villain" type="3" sum="0.30" cards="" />
            </round>
            <round no="2">
              <action no="4" player="Hero" type="5" sum="0.20" cards="" />
              <action no="5" player="Villain" type="4" sum="0" cards="" />
            </round>
            """
        )
        events = _events_from_hand_history(xml, STAKE_POLICY)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
