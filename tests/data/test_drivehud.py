"""Tests for the DriveHUD data adapter."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from poker_analytics.data.drivehud import DriveHudDataSource


class DriveHudDataSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = Path(tmp.name)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("create table sample (id integer primary key, value text)")
            conn.executemany(
                "insert into sample (value) values (?)",
                [("alpha",), ("beta",), ("gamma",)],
            )
        self.addCleanup(lambda: self.db_path.unlink(missing_ok=True))
        self.source = DriveHudDataSource(db_path=self.db_path)

    def test_is_available_true(self) -> None:
        self.assertTrue(self.source.is_available())

    def test_rows_returns_dicts(self) -> None:
        rows = list(self.source.rows("select id, value from sample order by id"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["value"], "alpha")
        self.assertEqual(rows[-1]["id"], 3)

    def test_scalar_returns_single_value(self) -> None:
        value = self.source.scalar("select count(*) from sample")
        self.assertEqual(value, 3)

    def test_count_helper(self) -> None:
        self.assertEqual(self.source.count("sample"), 3)

    def test_is_available_false_when_missing(self) -> None:
        missing = DriveHudDataSource(db_path=self.db_path.with_name("missing.db"))
        self.assertFalse(missing.is_available())


if __name__ == "__main__":
    unittest.main()
