"""Tests for flop loader service."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from poker_analytics.data.drivehud import DriveHudDataSource
from poker_analytics.services.flop_loader import load_flop_bet_summary


class FlopLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = Path(tmp.name)
        with sqlite3.connect(self.db_path) as conn:
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
        self.addCleanup(lambda: self.db_path.unlink(missing_ok=True))

    def test_load_flop_bet_summary_counts(self) -> None:
        source = DriveHudDataSource(db_path=self.db_path)
        summary = load_flop_bet_summary(source)
        self.assertEqual(summary["events"], 2)
        bucket_counts = {item["key"]: item["count"] for item in summary["buckets"]}
        self.assertEqual(bucket_counts["pct_40_60"], 1)
        self.assertEqual(bucket_counts["pct_60_80"], 1)
        texture_counts = {item["key"]: item["count"] for item in summary["textures"]}
        self.assertGreaterEqual(texture_counts["monotone"], 1)
        self.assertGreaterEqual(texture_counts["rainbow"], 1)

    def test_load_flop_bet_summary_missing_db(self) -> None:
        missing_source = DriveHudDataSource(db_path=self.db_path.with_name("missing.db"))
        summary = load_flop_bet_summary(missing_source)
        self.assertEqual(summary["events"], 0)
        self.assertTrue(all(item["count"] == 0 for item in summary["buckets"]))


if __name__ == "__main__":
    unittest.main()
