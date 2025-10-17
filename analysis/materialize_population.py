#!/usr/bin/env python3
"""Materialize population preflop baselines for faster querying.

This script builds summary tables for pool VPIP/PFR/3-bet by stake and by
stake/position, then rebinds the lightweight views to those tables. Run this
after ingest or whenever you want to refresh the baselines.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "warehouse" / "drivehud.sqlite"

CREATE_TABLE_STAKE = """
CREATE TABLE IF NOT EXISTS mv_population_by_stake (
  bb_c INTEGER PRIMARY KEY,
  player_hands INTEGER NOT NULL,
  vpip_yes INTEGER NOT NULL,
  pfr_yes INTEGER NOT NULL,
  three_bet_yes INTEGER NOT NULL,
  vpip_pct REAL NOT NULL,
  pfr_pct REAL NOT NULL,
  three_bet_pct REAL NOT NULL
);
"""

CREATE_TABLE_STAKE_POS = """
CREATE TABLE IF NOT EXISTS mv_population_by_stake_and_position (
  bb_c INTEGER NOT NULL,
  position TEXT NOT NULL,
  player_hands INTEGER NOT NULL,
  vpip_yes INTEGER NOT NULL,
  pfr_yes INTEGER NOT NULL,
  three_bet_yes INTEGER NOT NULL,
  vpip_pct REAL NOT NULL,
  pfr_pct REAL NOT NULL,
  three_bet_pct REAL NOT NULL,
  PRIMARY KEY (bb_c, position)
);
"""

INSERT_STAKE = """
INSERT INTO mv_population_by_stake
SELECT
  bb.bb_c AS bb_c,
  COUNT(*) AS player_hands,
  SUM(p.vpip) AS vpip_yes,
  SUM(p.pfr) AS pfr_yes,
  SUM(p.three_bet) AS three_bet_yes,
  ROUND(100.0 * SUM(p.vpip) / NULLIF(COUNT(*),0), 2) AS vpip_pct,
  ROUND(100.0 * SUM(p.pfr) / NULLIF(COUNT(*),0), 2) AS pfr_pct,
  ROUND(100.0 * SUM(p.three_bet) / NULLIF(COUNT(*),0), 2) AS three_bet_pct
FROM v_population_preflop_flags p
JOIN v_hand_bb bb ON bb.hand_id = p.hand_id
GROUP BY 1
ORDER BY 1;
"""

INSERT_STAKE_POS = """
INSERT INTO mv_population_by_stake_and_position
SELECT
  bb.bb_c AS bb_c,
  pos.position_pre AS position,
  COUNT(*) AS player_hands,
  SUM(p.vpip) AS vpip_yes,
  SUM(p.pfr) AS pfr_yes,
  SUM(p.three_bet) AS three_bet_yes,
  ROUND(100.0 * SUM(p.vpip) / NULLIF(COUNT(*),0), 2) AS vpip_pct,
  ROUND(100.0 * SUM(p.pfr) / NULLIF(COUNT(*),0), 2) AS pfr_pct,
  ROUND(100.0 * SUM(p.three_bet) / NULLIF(COUNT(*),0), 2) AS three_bet_pct
FROM v_population_preflop_flags p
JOIN v_hand_bb bb ON bb.hand_id = p.hand_id
JOIN (
    SELECT hand_id, seat_no, position_pre FROM seats
) AS pos ON pos.hand_id = p.hand_id AND pos.seat_no = p.seat_no
GROUP BY 1,2
ORDER BY 1,2;
"""

RECREATE_VIEW_STAKE = """
DROP VIEW IF EXISTS v_population_by_stake;
CREATE VIEW v_population_by_stake AS
SELECT * FROM mv_population_by_stake;
"""

RECREATE_VIEW_STAKE_POS = """
DROP VIEW IF EXISTS v_population_by_stake_and_position;
CREATE VIEW v_population_by_stake_and_position AS
SELECT * FROM mv_population_by_stake_and_position;
"""


def materialize(db_path: Path, analyze: bool = True) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-200000;")

        cur = conn.cursor()
        start = time.time()

        cur.execute("DROP TABLE IF EXISTS mv_population_by_stake;")
        cur.execute("DROP TABLE IF EXISTS mv_population_by_stake_and_position;")
        cur.execute(CREATE_TABLE_STAKE)
        cur.execute(CREATE_TABLE_STAKE_POS)

        cur.execute(INSERT_STAKE)
        cur.execute(INSERT_STAKE_POS)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_pop_stake_bb ON mv_population_by_stake(bb_c);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_pop_stake_pos ON mv_population_by_stake_and_position(bb_c, position);")

        conn.executescript(RECREATE_VIEW_STAKE)
        conn.executescript(RECREATE_VIEW_STAKE_POS)

        if analyze:
            cur.execute("ANALYZE mv_population_by_stake;")
            cur.execute("ANALYZE mv_population_by_stake_and_position;")

        conn.commit()
        elapsed = time.time() - start
        total_rows = cur.execute("SELECT COUNT(*) FROM mv_population_by_stake").fetchone()[0]
        total_combo = cur.execute("SELECT COUNT(*) FROM mv_population_by_stake_and_position").fetchone()[0]
        print(f"Materialized population baselines in {elapsed:.2f}s")
        print(f"  Stakes: {total_rows} rows")
        print(f"  Stake/position: {total_combo} rows")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize population preflop baselines")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to warehouse SQLite file")
    parser.add_argument("--no-analyze", action="store_true", help="Skip ANALYZE for faster execution")
    args = parser.parse_args()

    materialize(args.db, analyze=not args.no_analyze)


if __name__ == "__main__":
    main()
