"""Tests for flop response matrix builder helpers."""

from __future__ import annotations

import textwrap
import unittest

from poker_analytics.services.flop_response_matrix_builder import _events_from_hand_history


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
              <action no="4" player="Villain" type="4" sum="0" cards="" />
              <action no="5" player="Hero" type="5" sum="0.20" cards="" />
              <action no="6" player="Villain" type="0" sum="0" cards="" />
            </round>
            """
        )

        events = _events_from_hand_history(xml)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "cbet")
        self.assertTrue(event["in_position"])
        self.assertEqual(event["player_count"], 2)
        self.assertEqual(event["villain_outcome"], "fold")
        self.assertAlmostEqual(event["ratio"], 0.20 / 0.75, places=6)
        self.assertEqual(event["bucket_key"], "pct_25_40")

    def test_donk_event(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="2">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Hero</nickname>
                  <players>
                    <player seat="1" name="Hero" chips="10" dealer="0" />
                    <player seat="3" name="Aggressor" chips="10" dealer="1" />
                    <player seat="5" name="BigBlind" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="Hero" type="1" sum="0.05" cards="" />
                  <action no="1" player="BigBlind" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Hero" type="3" sum="0.05" cards="" />
                  <action no="3" player="Aggressor" type="23" sum="0.30" cards="" />
                  <action no="4" player="BigBlind" type="0" sum="0" cards="" />
                  <action no="5" player="Hero" type="3" sum="0.30" cards="" />
                </round>
                <round no="2">
                  <action no="6" player="Hero" type="5" sum="0.20" cards="" />
                  <action no="7" player="Aggressor" type="3" sum="0.20" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "donk")
        self.assertFalse(event["in_position"])
        self.assertEqual(event["player_count"], 2)
        self.assertEqual(event["villain_outcome"], "call")

    def test_stab_event(self) -> None:
        xml = textwrap.dedent(
            """
            <session sessioncode="0">
              <game gamecode="3">
                <general>
                  <gametype>Holdem NL $0.05/$0.10</gametype>
                  <nickname>Hero</nickname>
                  <players>
                    <player seat="1" name="SmallBlind" chips="10" dealer="0" />
                    <player seat="3" name="Hero" chips="10" dealer="1" />
                    <player seat="5" name="Aggressor" chips="10" dealer="0" />
                  </players>
                </general>
                <round no="0">
                  <action no="0" player="SmallBlind" type="1" sum="0.05" cards="" />
                  <action no="1" player="Aggressor" type="2" sum="0.10" cards="" />
                </round>
                <round no="1">
                  <action no="2" player="Aggressor" type="23" sum="0.30" cards="" />
                  <action no="3" player="Hero" type="3" sum="0.30" cards="" />
                  <action no="4" player="SmallBlind" type="0" sum="0" cards="" />
                </round>
                <round no="2">
                  <action no="5" player="Aggressor" type="4" sum="0" cards="" />
                  <action no="6" player="Hero" type="5" sum="0.20" cards="" />
                  <action no="7" player="Aggressor" type="0" sum="0" cards="" />
                </round>
              </game>
            </session>
            """
        ).strip()

        events = _events_from_hand_history(xml)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["bet_type"], "stab")
        self.assertTrue(event["in_position"])
        self.assertEqual(event["villain_outcome"], "fold")


if __name__ == "__main__":
    unittest.main()
