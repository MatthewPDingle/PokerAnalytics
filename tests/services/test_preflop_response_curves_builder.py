"""Tests for the response-curve builder."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from poker_analytics.services.preflop_response_curves_builder import build_response_curves


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE actions (
            hand_id TEXT,
            ordinal INTEGER,
            street TEXT,
            actor_seat INTEGER,
            action TEXT,
            to_amount_c REAL,
            inc_c REAL
        );

        CREATE TABLE seats (
            hand_id TEXT,
            seat_no INTEGER,
            position_pre TEXT,
            stack_start_c REAL
        );

        CREATE TABLE v_hand_bb (
            hand_id TEXT PRIMARY KEY,
            bb_c REAL
        );
        """
    )


def _insert_seats(conn: sqlite3.Connection, hand_id: str, stacks_bb: float = 100.0) -> None:
    positions = ["LJ", "HJ", "CO", "BTN", "SB", "BB"]
    stack_c = stacks_bb * 100  # big blind expressed in cents
    for seat_no, position in enumerate(positions, start=1):
        conn.execute(
            "INSERT INTO seats (hand_id, seat_no, position_pre, stack_start_c) VALUES (?, ?, ?, ?)",
            (hand_id, seat_no, position, stack_c),
        )


def _insert_actions_open_fold(conn: sqlite3.Connection, hand_id: str) -> None:
    # SB post 0.5 bb, BB post 1 bb, LJ raises to 3 bb, blinds fold, BB folds.
    rows = [
        (hand_id, 1, "preflop", 5, "post", 50, 50),
        (hand_id, 2, "preflop", 6, "post", 100, 100),
        (hand_id, 3, "preflop", 1, "raise", 300, 300),
        (hand_id, 4, "preflop", 2, "fold", 0, 0),
        (hand_id, 5, "preflop", 3, "fold", 0, 0),
        (hand_id, 6, "preflop", 4, "fold", 0, 0),
        (hand_id, 7, "preflop", 5, "fold", 0, 0),
        (hand_id, 8, "preflop", 6, "fold", 0, 0),
    ]
    conn.executemany(
        "INSERT INTO actions (hand_id, ordinal, street, actor_seat, action, to_amount_c, inc_c) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_actions_open_call(conn: sqlite3.Connection, hand_id: str) -> None:
    rows = [
        (hand_id, 1, "preflop", 5, "post", 50, 50),
        (hand_id, 2, "preflop", 6, "post", 100, 100),
        (hand_id, 3, "preflop", 2, "call", 100, 50),
        (hand_id, 4, "preflop", 1, "raise", 300, 250),
        (hand_id, 5, "preflop", 3, "fold", 0, 0),
        (hand_id, 6, "preflop", 4, "fold", 0, 0),
        (hand_id, 7, "preflop", 5, "fold", 0, 0),
        (hand_id, 8, "preflop", 6, "call", 300, 200),
    ]
    conn.executemany(
        "INSERT INTO actions (hand_id, ordinal, street, actor_seat, action, to_amount_c, inc_c) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_actions_squeeze(conn: sqlite3.Connection, hand_id: str) -> None:
    rows = [
        (hand_id, 1, "preflop", 5, "post", 50, 50),
        (hand_id, 2, "preflop", 6, "post", 100, 100),
        (hand_id, 3, "preflop", 1, "raise", 250, 250),
        (hand_id, 4, "preflop", 2, "call", 250, 150),
        (hand_id, 5, "preflop", 3, "call", 250, 150),
        (hand_id, 6, "preflop", 4, "raise", 1100, 850),
        (hand_id, 7, "preflop", 5, "fold", 0, 0),
        (hand_id, 8, "preflop", 6, "fold", 0, 0),
        (hand_id, 9, "preflop", 1, "call", 1100, 850),
        (hand_id, 10, "preflop", 2, "raise", 2500, 2250),
    ]
    conn.executemany(
        "INSERT INTO actions (hand_id, ordinal, street, actor_seat, action, to_amount_c, inc_c) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


class ResponseCurveBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "drivehud.db"
        with sqlite3.connect(self.db_path) as conn:
            _create_schema(conn)
            for hand_id in ("H1", "H2", "H3"):
                _insert_seats(conn, hand_id)
                conn.execute("INSERT INTO v_hand_bb (hand_id, bb_c) VALUES (?, ?)", (hand_id, 100))
            _insert_actions_open_fold(conn, "H1")
            _insert_actions_open_call(conn, "H2")
            _insert_actions_squeeze(conn, "H3")
            conn.commit()

        self._env_backup = os.environ.get("DRIVEHUD_DB_PATH")
        os.environ["DRIVEHUD_DB_PATH"] = str(self.db_path)

    def tearDown(self) -> None:
        if self._env_backup is None:
            os.environ.pop("DRIVEHUD_DB_PATH", None)
        else:
            os.environ["DRIVEHUD_DB_PATH"] = self._env_backup
        self._tmpdir.cleanup()

    def test_builder_produces_scenarios(self) -> None:
        scenarios = build_response_curves()

        self.assertTrue(scenarios, "expected at least one response-curve scenario")
        self.assertTrue(all(s.stack_bucket_key for s in scenarios))
        self.assertTrue(all(s.pot_bucket_key for s in scenarios))
        self.assertTrue(all(s.players_behind >= 0 for s in scenarios))
        self.assertTrue(all(s.effective_stack_bb >= 0 for s in scenarios))
        hero_positions = {scenario.hero_position for scenario in scenarios}
        self.assertIn("LJ", hero_positions)
        self.assertIn("BTN", hero_positions)

        lj_scenarios = [s for s in scenarios if s.hero_position == "LJ" and s.situation_key == "folded_to_hero"]
        self.assertTrue(lj_scenarios, "missing LJ open scenario")
        self.assertTrue(lj_scenarios[0].players_behind > 0)
        lj_points = lj_scenarios[0].points
        self.assertTrue(any(point.bucket_key == "pct_125_200" for point in lj_points))
        self.assertIn(lj_scenarios[0].stack_bucket_key, {"bb_60_100", "bb_100_plus"})

        btn_scenarios = [s for s in scenarios if s.hero_position == "BTN" and s.situation_key == "facing_raise_with_callers"]
        self.assertTrue(btn_scenarios, "missing BTN squeeze scenario")
        self.assertGreaterEqual(btn_scenarios[0].players_behind, 1)
        situation_keys = {scenario.situation_key for scenario in scenarios}
        self.assertIn("facing_limpers", situation_keys)

    def test_builder_parses_hand_histories_when_tables_missing(self) -> None:
        self._tmpdir.cleanup()
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "drivehud.db"
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE HandHistories (
                    HandHistoryId INTEGER PRIMARY KEY,
                    HandHistory TEXT
                );
                """
            )
            xml = """
<session sessioncode=\"0\">
  <general>
    <nickname>Hero</nickname>
    <gametype>Holdem NL $0.50/$1.00</gametype>
  </general>
  <game>
    <general>
      <players>
        <player seat=\"1\" name=\"Hero\" chips=\"100\" dealer=\"0\"/>
        <player seat=\"2\" name=\"Villain1\" chips=\"100\" dealer=\"0\"/>
        <player seat=\"3\" name=\"Villain2\" chips=\"100\" dealer=\"0\"/>
        <player seat=\"4\" name=\"Villain3\" chips=\"100\" dealer=\"0\"/>
        <player seat=\"5\" name=\"Villain4\" chips=\"100\" dealer=\"1\"/>
        <player seat=\"6\" name=\"Villain5\" chips=\"100\" dealer=\"0\"/>
      </players>
    </general>
    <round no=\"0\">
      <action no=\"0\" player=\"Villain4\" type=\"1\" sum=\"0.5\" cards=\"\" />
      <action no=\"1\" player=\"Villain5\" type=\"2\" sum=\"1.0\" cards=\"\" />
    </round>
    <round no=\"1\">
      <action no=\"2\" player=\"Villain2\" type=\"3\" sum=\"1.0\" cards=\"\" />
      <action no=\"3\" player=\"Hero\" type=\"23\" sum=\"3.0\" cards=\"\" />
      <action no=\"4\" player=\"Villain3\" type=\"3\" sum=\"3.0\" cards=\"\" />
    </round>
  </game>
</session>
"""
            conn.execute(
                "INSERT INTO HandHistories (HandHistoryId, HandHistory) VALUES (?, ?)",
                (1, xml),
            )
            conn.commit()

        environ_backup = os.environ.get("DRIVEHUD_DB_PATH")
        os.environ["DRIVEHUD_DB_PATH"] = str(db_path)
        try:
            scenarios = build_response_curves()
        finally:
            if environ_backup is None:
                os.environ.pop("DRIVEHUD_DB_PATH", None)
            else:
                os.environ["DRIVEHUD_DB_PATH"] = environ_backup

        self.assertTrue(scenarios, "expected scenarios from XML parsing path")
        hero_positions = {scenario.hero_position for scenario in scenarios}
        self.assertIn("UTG", hero_positions)
        situation_keys = {scenario.situation_key for scenario in scenarios}
        self.assertIn("facing_limpers", situation_keys)
        self.assertTrue(all(s.players_behind >= 0 for s in scenarios))



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
