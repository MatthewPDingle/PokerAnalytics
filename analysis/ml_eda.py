#!/usr/bin/env python3
"""Lightweight exploratory data analysis for player feature extracts.

Summarises hand volumes, key statistics, and correlation hints without
requiring pandas or numpy. Intended for quick CLI inspection before running
full modelling notebooks.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis import ml_train

KEY_STATS = [
    "bb_per_100",
    "vpip_pct",
    "pfr_pct",
    "vpip_pfr_gap_pct",
    "three_bet_pct",
    "cold_call_pct",
    "fold_to_3bet_pct",
    "cbet_flop_pct",
    "cbet_turn_pct",
    "cbet_river_pct",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarise ML feature dataset")
    parser.add_argument(
        "--features",
        type=Path,
        default=ml_train.DEFAULT_FEATURES,
        help="Path to feature CSV/Parquet file",
    )
    parser.add_argument("--min-hands", type=int, default=2000, help="Minimum hands per player")
    parser.add_argument("--top-n", type=int, default=10, help="How many winners/losers to list")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON file to persist summary data",
    )
    return parser.parse_args(argv)


def summarise_metric(rows: List[Dict[str, str]], key: str) -> Dict[str, float]:
    values: List[float] = []
    for row in rows:
        try:
            values.append(float(row.get(key, 0.0) or 0.0))
        except ValueError:
            values.append(0.0)
    if not values:
        return {"count": 0}
    values.sort()
    n = len(values)
    return {
        "count": n,
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "stdev": round(statistics.pstdev(values), 3) if n > 1 else 0.0,
        "min": round(values[0], 3),
        "q1": round(values[int(0.25 * (n - 1))], 3),
        "q3": round(values[int(0.75 * (n - 1))], 3),
        "max": round(values[-1], 3),
    }


def top_players(rows: List[Dict[str, str]], key: str, n: int, reverse: bool) -> List[Dict[str, float]]:
    scored = []
    for row in rows:
        pid = row.get("player_id", "unknown")
        try:
            value = float(row.get(key, 0.0) or 0.0)
        except ValueError:
            value = 0.0
        scored.append((value, pid, float(row.get("hands_total", 0.0) or 0.0)))
    scored.sort(reverse=reverse, key=lambda item: item[0])
    return [
        {"player_id": pid, key: round(value, 3), "hands": int(hands)}
        for value, pid, hands in scored[:n]
    ]


def total_hands(rows: Sequence[Dict[str, str]]) -> float:
    total = 0.0
    for row in rows:
        try:
            total += float(row.get("hands_total", 0.0) or 0.0)
        except ValueError:
            continue
    return total


def human_print(summary: Dict[str, object]) -> None:
    print(f"Players analysed: {summary['players']['count']}")
    print(
        "Hands per player (median/mean/max):",
        summary["players"]["hands_median"],
        summary["players"]["hands_mean"],
        summary["players"]["hands_max"],
    )
    print(f"Total hands in sample: {summary['players']['hands_total']:.0f}")

    print("\nTop winners (bb/100):")
    for row in summary["leaderboards"]["top_winners"]:
        print(f"  {row['player_id']:<16} {row['bb_per_100']:>6.2f} bb/100 ({row['hands']} hands)")
    print("\nBiggest losers (bb/100):")
    for row in summary["leaderboards"]["top_losers"]:
        print(f"  {row['player_id']:<16} {row['bb_per_100']:>6.2f} bb/100 ({row['hands']} hands)")

    print("\nKey metric summaries:")
    for key, stats in summary["metrics"].items():
        if not isinstance(stats, dict):
            continue
        print(
            f"  {key:<18} mean={stats['mean']:>6.2f} median={stats['median']:>6.2f}"
            f" q1={stats['q1']:>6.2f} q3={stats['q3']:>6.2f}"
        )

    print("\nTop correlations with bb/100 (weighted Pearson):")
    for entry in summary["correlations"][:10]:
        print(f"  {entry['feature']:<24} {entry['pearson']:>6.3f}")


def build_summary(rows: List[Dict[str, str]], cfg: ml_train.TrainingConfig, top_n: int) -> Dict[str, object]:
    reg_data = ml_train.build_regression_dataset(rows, cfg)
    correlations = [
        {"feature": feat, "pearson": round(value, 4)}
        for feat, value in ml_train.compute_feature_correlations(reg_data)
    ]

    hands_values = [float(row.get("hands_total", 0.0) or 0.0) for row in rows]
    hands_values.sort()
    player_summary = {
        "count": len(rows),
        "hands_total": round(total_hands(rows), 1),
        "hands_mean": round(statistics.mean(hands_values), 1) if hands_values else 0.0,
        "hands_median": round(statistics.median(hands_values), 1) if hands_values else 0.0,
        "hands_max": round(max(hands_values), 1) if hands_values else 0.0,
    }

    metric_summary = {key: summarise_metric(rows, key) for key in KEY_STATS}

    leaderboards = {
        "top_winners": top_players(rows, "bb_per_100", top_n, True),
        "top_losers": top_players(rows, "bb_per_100", top_n, False),
        "vpip_high": top_players(rows, "vpip_pct", top_n, True),
        "vpip_low": top_players(rows, "vpip_pct", top_n, False),
    }

    return {
        "players": player_summary,
        "metrics": metric_summary,
        "leaderboards": leaderboards,
        "correlations": correlations,
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    rows = ml_train.load_features(args.features)
    filtered_rows = ml_train.filter_rows(rows, args.min_hands)
    if not filtered_rows:
        raise SystemExit("No rows passed the minimum hand filter")

    cfg = ml_train.TrainingConfig(
        features_path=args.features,
        out_dir=ml_train.DEFAULT_OUT_DIR,
        min_hands=args.min_hands,
        tasks=("regression", "classification"),
        weight_strategy="log_hand_count",
        k_folds=5,
        seed=2024,
    )
    summary = build_summary(filtered_rows, cfg, args.top_n)
    human_print(summary)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nWrote summary JSON to {args.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
