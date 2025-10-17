"""Adapter for DriveHUD SQLite databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from poker_analytics.config import DataPaths, build_data_paths
from poker_analytics.db import connect_readonly


@dataclass(frozen=True)
class DriveHudDataSource:
    """Read-only facade over the DriveHUD warehouse."""

    db_path: Path

    @classmethod
    def from_defaults(cls) -> "DriveHudDataSource":
        paths = build_data_paths()
        return cls(db_path=paths.drivehud_db)

    def is_available(self) -> bool:
        return self.db_path.exists()

    def rows(self, query: str, params: Sequence[object] | None = None) -> Iterator[dict[str, object]]:
        if params is None:
            params = ()
        with connect_readonly(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            for row in cursor:
                yield dict(row)

    def scalar(self, query: str, params: Sequence[object] | None = None) -> object | None:
        params = params or ()
        with connect_readonly(self.db_path) as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
        return result[0] if result else None

    def count(self, table: str) -> int:
        value = self.scalar(f"select count(*) from {table}")
        return int(value or 0)


__all__ = ["DriveHudDataSource"]
