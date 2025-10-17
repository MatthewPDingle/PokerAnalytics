"""Integration tests exercising DriveHUD adapter end-to-end."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from poker_analytics.data.drivehud import DriveHudDataSource


class DriveHudIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        cls.db_path = Path(tmp.name)
        with sqlite3.connect(cls.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE hands (
                    hand_id TEXT PRIMARY KEY,
                    board_flop TEXT
                );
                CREATE TABLE seats (
                    hand_id TEXT,
                    seat_no INTEGER,
                    player_name TEXT,
                    is_hero INTEGER
                );
                CREATE TABLE actions (
                    hand_id TEXT,
                    street TEXT,
                    actor TEXT,
                    action TEXT,
                    amount REAL
                );

                INSERT INTO hands VALUES
                    ('H1', 'Ah Kh Qh'),
                    ('H2', '7c 8d 9s');

                INSERT INTO seats VALUES
                    ('H1', 1, 'Hero', 1),
                    ('H1', 2, 'Villain', 0),
                    ('H2', 1, 'Hero', 1),
                    ('H2', 3, 'Villain2', 0);

                INSERT INTO actions VALUES
                    ('H1', 'flop', 'Hero', 'bet', 0.6),
                    ('H1', 'flop', 'Villain', 'call', 0.6),
                    ('H2', 'flop', 'Hero', 'bet', 0.4),
                    ('H2', 'flop', 'Villain2', 'fold', 0.0);
                """
            )
        cls.source = DriveHudDataSource(db_path=cls.db_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_path.unlink(missing_ok=True)

    def test_fetch_flop_bets_with_board(self) -> None:
        query = """
            SELECT h.hand_id, h.board_flop, a.amount
            FROM hands h
            JOIN actions a ON a.hand_id = h.hand_id
            WHERE a.street = 'flop' AND a.actor = 'Hero'
            ORDER BY h.hand_id
        """
        rows = list(self.source.rows(query))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["board_flop"], 'Ah Kh Qh')
        self.assertAlmostEqual(rows[0]["amount"], 0.6)

    def test_hero_flop_bet_percentage(self) -> None:
        query = """
            SELECT h.hand_id, a.amount,
                   CASE WHEN h.board_flop = 'Ah Kh Qh' THEN 1.0 ELSE 0.8 END AS pot
            FROM hands h
            JOIN actions a ON a.hand_id = h.hand_id
            WHERE a.street = 'flop' AND a.actor = 'Hero'
        """
        ratios = [row["amount"] / row["pot"] for row in self.source.rows(query)]
        self.assertEqual(len(ratios), 2)
        self.assertGreater(ratios[0], ratios[1])

    def test_count_tables(self) -> None:
        self.assertEqual(self.source.count("hands"), 2)
        self.assertEqual(self.source.count("actions"), 4)


if __name__ == "__main__":
    unittest.main()
