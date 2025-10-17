#!/usr/bin/env python3
"""SHAP helper for LightGBM models produced by analysis/ml_train.py.

If LightGBM + numpy + shap are available, this script loads the latest model
run, computes global SHAP importance, and emits JSON/Parquet summaries..
Otherwise it prints actionable instructions and exits cleanly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis import ml_train

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover
    np = None  # type: ignore

try:  # pragma: no cover
    import lightgbm as lgb  # type: ignore
except ImportError:  # pragma: no cover
    lgb = None  # type: ignore

try:  # pragma: no cover
    import shap  # type: ignore
except ImportError:  # pragma: no cover
    shap = None  # type: ignore

try:  # pragma: no cover
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute SHAP values for trained models")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=ml_train.DEFAULT_OUT_DIR,
        help="Directory containing timestamped model runs",
    )
    parser.add_argument(
        "--run",
        type=Path,
        default=None,
        help="Specific run directory (default: latest under --models-dir)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of top features to keep in exported summary",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("analysis/reports/shap_summary.json"),
        help="Path to write SHAP summary JSON",
    )
    parser.add_argument(
        "--out-parquet",
        type=Path,
        default=Path("analysis/reports/shap_summary.parquet"),
        help="Optional Parquet output (requires pandas)",
    )
    parser.add_argument(
        "--min-hands",
        type=int,
        default=2000,
        help="Rebuild dataset with this minimum hand count for consistency",
    )
    return parser.parse_args(argv)


def ensure_dependencies() -> None:
    missing = []
    if np is None:
        missing.append("numpy")
    if lgb is None:
        missing.append("lightgbm")
    if shap is None:
        missing.append("shap")
    if missing:
        raise SystemExit(
            "Cannot compute SHAP values because the following packages are missing: "
            + ", ".join(missing)
            + ". Install them and re-run."
        )


def resolve_run_dir(models_dir: Path, explicit: Optional[Path]) -> Path:
    if explicit:
        if explicit.is_dir():
            return explicit
        candidate = models_dir / explicit
        if candidate.is_dir():
            return candidate
        raise SystemExit(f"Run directory not found: {explicit}")
    runs = [p for p in models_dir.iterdir() if p.is_dir()]
    if not runs:
        raise SystemExit(f"No runs found under {models_dir}")
    return sorted(runs)[-1]


def load_summary(run_dir: Path) -> dict:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"summary.json missing in {run_dir}")
    return json.loads(summary_path.read_text())


def shap_summary(run_dir: Path, args: argparse.Namespace) -> None:
    ensure_dependencies()
    summary = load_summary(run_dir)
    regression_metrics = summary.get("metrics", {}).get("regression")
    if not regression_metrics or regression_metrics.get("backend") != "lightgbm":
        raise SystemExit(
            "Regression model is not a LightGBM booster. Train with LightGBM before running SHAP."
        )

    features_path = Path(summary["config"]["features_path"])
    rows = ml_train.load_features(features_path)
    filtered_rows = ml_train.filter_rows(rows, args.min_hands)
    if not filtered_rows:
        raise SystemExit("No rows available after applying min-hands filter for SHAP")

    cfg = ml_train.TrainingConfig(
        features_path=features_path,
        out_dir=ml_train.DEFAULT_OUT_DIR,
        min_hands=args.min_hands,
        tasks=("regression", "classification"),
        weight_strategy=summary["config"].get("weight_strategy", "log_hand_count"),
        k_folds=summary["config"].get("k_folds", 5),
        seed=summary["config"].get("seed", 2024),
    )
    regression_data = ml_train.build_regression_dataset(filtered_rows, cfg)

    model_path = run_dir / "regression" / "lightgbm_model.txt"
    if not model_path.exists():
        raise SystemExit(f"LightGBM model file not found at {model_path}")

    booster = lgb.Booster(model_file=str(model_path))
    X = np.array(regression_data.matrix, dtype=float)
    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]

    mean_abs = np.mean(np.abs(shap_values), axis=0)
    top_idx = np.argsort(mean_abs)[::-1][: args.top_n]
    feature_names = np.array(regression_data.feature_names)[top_idx]
    top_importance = mean_abs[top_idx]

    summary_rows = [
        {"feature": feature, "mean_abs_shap": float(value)}
        for feature, value in zip(feature_names, top_importance)
    ]

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")
    print(f"Wrote SHAP summary JSON to {args.out_json}")

    if args.out_parquet:
        if pd is None:
            print("pandas not installed; skipping Parquet export")
        else:
            args.out_parquet.parent.mkdir(parents=True, exist_ok=True)
            try:
                pd.DataFrame(summary_rows).to_parquet(args.out_parquet, index=False)
                print(f"Wrote SHAP summary Parquet to {args.out_parquet}")
            except Exception as exc:
                print(f"Parquet export skipped: {exc}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    run_dir = resolve_run_dir(args.models_dir, args.run)
    shap_summary(run_dir, args)


if __name__ == "__main__":  # pragma: no cover
    main()
