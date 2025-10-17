#!/usr/bin/env python3
"""Summarize hero fold-to-3-bet tendencies by position and stake."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "drivehud.sqlite"

POSITION_QUERY = """
WITH hero_ext AS (
    SELECT e.*, s.position_pre AS position, bb.bb_c AS bb
    FROM v_hero_preflop_ext e
    JOIN seats s ON s.hand_id=e.hand_id AND s.is_hero=1
    JOIN v_hand_bb bb ON bb.hand_id=e.hand_id
    WHERE e.pfr=1
)
SELECT position,
       COUNT(*) AS opens,
       SUM(faced_3b) AS faced,
       SUM(fold_to_3b) AS folded,
       ROUND(100.0 * SUM(fold_to_3b) / NULLIF(SUM(faced_3b),0), 2) AS fold_pct
FROM hero_ext
GROUP BY position
ORDER BY position;
"""

STAKE_QUERY = """
WITH hero_ext AS (
    SELECT e.*, s.position_pre AS position, bb.bb_c AS bb
    FROM v_hero_preflop_ext e
    JOIN seats s ON s.hand_id=e.hand_id AND s.is_hero=1
    JOIN v_hand_bb bb ON bb.hand_id=e.hand_id
    WHERE e.pfr=1
)
SELECT bb,
       COUNT(*) AS opens,
       SUM(faced_3b) AS faced,
       SUM(fold_to_3b) AS folded,
       ROUND(100.0 * SUM(fold_to_3b) / NULLIF(SUM(faced_3b),0), 2) AS fold_pct
FROM hero_ext
GROUP BY bb
ORDER BY bb;
"""


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Warehouse not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        print("Fold-to-3B by position:")
        cur.execute(POSITION_QUERY)
        rows = cur.fetchall()
        print(f"{'Pos':<6}{'Opens':>8}{'Faced':>8}{'Fold':>8}{'Fold%':>8}")
        for pos, opens, faced, folded, pct in rows:
            pct_str = f"{pct:.2f}" if pct is not None else "--"
            print(f"{pos:<6}{opens:8d}{faced:8d}{folded:8d}{pct_str:>8}")
        print()

        print("Fold-to-3B by stake:")
        cur.execute(STAKE_QUERY)
        rows = cur.fetchall()
        print(f"{'BB':<6}{'Opens':>8}{'Faced':>8}{'Fold':>8}{'Fold%':>8}")
        for bb, opens, faced, folded, pct in rows:
            pct_str = f"{pct:.2f}" if pct is not None else "--"
            print(f"{bb:<6}{opens:8d}{faced:8d}{folded:8d}{pct_str:>8}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
