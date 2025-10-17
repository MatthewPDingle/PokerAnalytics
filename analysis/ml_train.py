#!/usr/bin/env python3
"""Train interpretable models on per-player feature extracts.

This script prefers LightGBM (or ElasticNet/LogisticRegression) when the
libraries are present. In bare environments it gracefully falls back to
weighted mean/majority baselines so the coaching workflow still runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Optional dependencies -----------------------------------------------------
try:  # pragma: no cover - availability checked dynamically
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - handled downstream
    np = None  # type: ignore

try:  # pragma: no cover - availability checked dynamically
    import lightgbm as lgb  # type: ignore
except ImportError:  # pragma: no cover - handled downstream
    lgb = None  # type: ignore

SKLEARN_AVAILABLE = False
if np is not None:  # pragma: no cover - avoid ImportError noise when numpy missing
    try:
        from sklearn.linear_model import ElasticNet, LogisticRegression  # type: ignore
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # type: ignore
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score  # type: ignore
        from sklearn.preprocessing import StandardScaler  # type: ignore
        SKLEARN_AVAILABLE = True
    except ImportError:  # pragma: no cover - handled by fallbacks
        SKLEARN_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = PROJECT_ROOT / "analysis" / "features" / "players.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "analysis" / "models"

EXCLUDED_FEATURES = {"bb_per_100", "net_bb_total"}


@dataclass
class TrainingConfig:
    features_path: Path
    out_dir: Path
    min_hands: int
    tasks: Tuple[str, ...]
    weight_strategy: str
    k_folds: int
    seed: int


@dataclass
class RegressionDataset:
    feature_names: List[str]
    matrix: List[List[float]]
    target: List[float]
    weights: List[float]
    player_ids: List[str]


@dataclass
class ClassificationDataset:
    feature_names: List[str]
    matrix: List[List[float]]
    labels: List[int]
    weights: List[float]
    thresholds: Tuple[float, float]
    player_ids: List[str]


# ---------------------------------------------------------------------------
# Argument parsing / I/O helpers


def parse_args(argv: Optional[Sequence[str]] = None) -> TrainingConfig:
    parser = argparse.ArgumentParser(description="Train ML models for player success analysis")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Path to feature CSV/Parquet file")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Directory to store model artefacts")
    parser.add_argument("--min-hands", type=int, default=2000, help="Minimum hands per player to include")
    parser.add_argument(
        "--tasks",
        choices=["regression", "classification", "both"],
        default="both",
        help="Targets to train",
    )
    parser.add_argument(
        "--weight-strategy",
        choices=["hand_count", "log_hand_count"],
        default="log_hand_count",
        help="Row weighting policy",
    )
    parser.add_argument("--k-folds", type=int, default=5, help="Cross-validation folds (>=1)")
    parser.add_argument("--seed", type=int, default=2024, help="Random seed for shuffling")
    args = parser.parse_args(argv)

    if not args.features.exists():
        raise SystemExit(f"Feature file not found: {args.features}")

    tasks: Tuple[str, ...] = ("regression", "classification") if args.tasks == "both" else (args.tasks,)
    return TrainingConfig(
        features_path=args.features,
        out_dir=args.out_dir,
        min_hands=args.min_hands,
        tasks=tasks,
        weight_strategy=args.weight_strategy,
        k_folds=max(args.k_folds, 1),
        seed=args.seed,
    )


def load_features(path: Path) -> List[Dict[str, str]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return [row for row in reader]
    if path.suffix.lower() in {".parquet", ".pq"}:  # pragma: no cover - requires pandas
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional path
            raise SystemExit("Parquet support requires pandas. Install pandas or output CSV instead.") from exc
        df = pd.read_parquet(path)
        return [dict(record) for record in df.to_dict(orient="records")]
    raise SystemExit(f"Unsupported feature file format: {path.suffix}")


def filter_rows(rows: List[Dict[str, str]], min_hands: int) -> List[Dict[str, str]]:
    filtered: List[Dict[str, str]] = []
    for row in rows:
        try:
            hands = float(row.get("hands_total", 0.0))
        except ValueError:
            hands = 0.0
        if hands >= min_hands:
            filtered.append(row)
    return filtered


# ---------------------------------------------------------------------------
# Dataset construction


def parse_numeric(row: Dict[str, str]) -> Dict[str, float]:
    numeric: Dict[str, float] = {}
    for key, value in row.items():
        if key == "player_id":
            continue
        if value is None or value == "":
            numeric[key] = 0.0
            continue
        try:
            numeric[key] = float(value)
        except ValueError:
            numeric[key] = 0.0
    return numeric


def compute_weight(row: Dict[str, str], strategy: str) -> float:
    try:
        hands = float(row.get("hands_total", 0.0))
    except ValueError:
        hands = 0.0
    hands = max(hands, 1.0)
    if strategy == "hand_count":
        return hands
    return math.log(hands + 1.0)


def feature_columns(rows: List[Dict[str, str]]) -> List[str]:
    keys: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key == "player_id" or key in EXCLUDED_FEATURES:
                continue
            keys.add(key)
    return sorted(keys)


def build_regression_dataset(rows: List[Dict[str, str]], cfg: TrainingConfig) -> RegressionDataset:
    features = feature_columns(rows)
    matrix: List[List[float]] = []
    targets: List[float] = []
    weights: List[float] = []
    player_ids: List[str] = []

    for row in rows:
        numeric = parse_numeric(row)
        matrix.append([numeric.get(col, 0.0) for col in features])
        targets.append(numeric.get("bb_per_100", 0.0))
        weights.append(compute_weight(row, cfg.weight_strategy))
        player_ids.append(row.get("player_id", "unknown"))

    return RegressionDataset(feature_names=features, matrix=matrix, target=targets, weights=weights, player_ids=player_ids)


def compute_quantiles(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ordered = sorted(values)
    n = len(ordered)
    q1_idx = max(int(0.25 * (n - 1)), 0)
    q3_idx = max(int(0.75 * (n - 1)), 0)
    return ordered[q1_idx], ordered[q3_idx]


def build_classification_dataset(reg_data: RegressionDataset) -> ClassificationDataset:
    q1, q3 = compute_quantiles(reg_data.target)
    matrix: List[List[float]] = []
    labels: List[int] = []
    weights: List[float] = []
    players: List[str] = []

    for feats, target, weight, player in zip(reg_data.matrix, reg_data.target, reg_data.weights, reg_data.player_ids):
        if target <= q1:
            matrix.append(feats.copy())
            labels.append(0)
            weights.append(weight)
            players.append(player)
        elif target >= q3:
            matrix.append(feats.copy())
            labels.append(1)
            weights.append(weight)
            players.append(player)
    return ClassificationDataset(
        feature_names=reg_data.feature_names,
        matrix=matrix,
        labels=labels,
        weights=weights,
        thresholds=(q1, q3),
        player_ids=players,
    )


# ---------------------------------------------------------------------------
# Metric helpers


def weighted_rmse(y_true: Iterable[float], y_pred: Iterable[float], weights: Iterable[float]) -> float:
    total = 0.0
    error = 0.0
    for yt, yp, w in zip(y_true, y_pred, weights):
        total += w
        error += w * (yt - yp) ** 2
    return math.sqrt(error / total) if total else float("nan")


def weighted_mae(y_true: Iterable[float], y_pred: Iterable[float], weights: Iterable[float]) -> float:
    total = 0.0
    error = 0.0
    for yt, yp, w in zip(y_true, y_pred, weights):
        total += w
        error += w * abs(yt - yp)
    return error / total if total else float("nan")


def weighted_r2(y_true: Iterable[float], y_pred: Iterable[float], weights: Iterable[float]) -> float:
    y_true = list(y_true)
    y_pred = list(y_pred)
    weights = list(weights)
    total = sum(weights)
    if total == 0:
        return float("nan")
    mean_y = sum(y * w for y, w in zip(y_true, weights)) / total
    ss_res = sum(w * (yt - yp) ** 2 for yt, yp, w in zip(y_true, y_pred, weights))
    ss_tot = sum(w * (yt - mean_y) ** 2 for yt, w in zip(y_true, weights))
    if ss_tot == 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def weighted_classification_metrics(labels: Iterable[int], preds: Iterable[int], weights: Iterable[float]) -> Dict[str, float]:
    tp = tn = fp = fn = 0.0
    for label, pred, weight in zip(labels, preds, weights):
        if label == 1 and pred == 1:
            tp += weight
        elif label == 0 and pred == 0:
            tn += weight
        elif label == 0 and pred == 1:
            fp += weight
        else:
            fn += weight
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else float("nan")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else float("nan")
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


# ---------------------------------------------------------------------------
# Baseline models (no ML dependencies)


def regression_baseline(data: RegressionDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    total_weight = sum(data.weights)
    mean_target = sum(t * w for t, w in zip(data.target, data.weights)) / total_weight if total_weight else 0.0
    rmse = weighted_rmse(data.target, [mean_target] * len(data.target), data.weights)
    mae = weighted_mae(data.target, [mean_target] * len(data.target), data.weights)
    r2 = weighted_r2(data.target, [mean_target] * len(data.target), data.weights)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "prediction": mean_target,
        "weight_strategy": cfg.weight_strategy,
    }
    (artifact_dir / "baseline.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "rmse": round(rmse, 3) if not math.isnan(rmse) else float("nan"),
        "mae": round(mae, 3) if not math.isnan(mae) else float("nan"),
        "r2": round(r2, 3) if not math.isnan(r2) else float("nan"),
        "baseline": True,
        "backend": "weighted_mean",
    }


def classification_baseline(data: ClassificationDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    q1, q3 = data.thresholds
    if not data.labels:
        payload = {
            "prediction": 0,
            "positive_rate": 0.0,
            "thresholds": {"q1": q1, "q3": q3},
            "weight_strategy": cfg.weight_strategy,
            "note": "Not enough labelled samples for classification target.",
        }
        (artifact_dir / "baseline.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "accuracy": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "f1": float("nan"),
            "baseline": True,
            "backend": "majority_class",
            "samples": 0,
            "thresholds": {"q1": q1, "q3": q3},
        }

    positives = sum(w for label, w in zip(data.labels, data.weights) if label == 1)
    total = sum(data.weights)
    positive_rate = positives / total if total else 0.0
    prediction = 1 if positive_rate >= 0.5 else 0

    tp = sum(w for label, w in zip(data.labels, data.weights) if label == 1 and prediction == 1)
    tn = sum(w for label, w in zip(data.labels, data.weights) if label == 0 and prediction == 0)
    fp = sum(w for label, w in zip(data.labels, data.weights) if label == 0 and prediction == 1)
    fn = sum(w for label, w in zip(data.labels, data.weights) if label == 1 and prediction == 0)

    accuracy = (tp + tn) / total if total else float("nan")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else float("nan")

    payload = {
        "prediction": prediction,
        "positive_rate": positive_rate,
        "thresholds": {"q1": q1, "q3": q3},
        "weight_strategy": cfg.weight_strategy,
    }
    (artifact_dir / "baseline.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "accuracy": round(accuracy, 3) if not math.isnan(accuracy) else float("nan"),
        "precision": round(precision, 3) if not math.isnan(precision) else float("nan"),
        "recall": round(recall, 3) if not math.isnan(recall) else float("nan"),
        "f1": round(f1, 3) if not math.isnan(f1) else float("nan"),
        "baseline": True,
        "backend": "majority_class",
        "samples": len(data.labels),
        "thresholds": {"q1": q1, "q3": q3},
    }


# ---------------------------------------------------------------------------
# Advanced models (LightGBM / ElasticNet / LogisticRegression)


def make_folds(n_samples: int, k: int, seed: int) -> List[List[int]]:
    indices = list(range(n_samples))
    random.Random(seed).shuffle(indices)
    if k <= 1 or k > n_samples:
        return [indices]
    folds: List[List[int]] = []
    base = n_samples // k
    remainder = n_samples % k
    start = 0
    for i in range(k):
        size = base + (1 if i < remainder else 0)
        if size == 0:
            continue
        folds.append(indices[start : start + size])
        start += size
    if not folds:
        folds.append(indices)
    return folds


def train_regression_lightgbm(data: RegressionDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    if lgb is None or np is None:  # pragma: no cover - guarded in caller
        raise RuntimeError("LightGBM or numpy unavailable")
    if len(data.target) < 10:  # avoid overfitting tiny samples
        raise RuntimeError("Not enough samples for LightGBM regression")

    X = np.array(data.matrix, dtype=float)
    y = np.array(data.target, dtype=float)
    w = np.array(data.weights, dtype=float)

    folds = make_folds(len(y), min(cfg.k_folds, len(y)), cfg.seed)
    rmse_scores: List[float] = []
    mae_scores: List[float] = []
    best_iterations: List[int] = []

    min_leaf = max(5, min(50, max(len(y) // 4, 1)))

    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "min_data_in_leaf": min_leaf,
        "verbosity": -1,
        "seed": cfg.seed,
    }

    def make_callbacks(rounds: int) -> List:
        callbacks = []
        if rounds > 0:
            if hasattr(lgb, "early_stopping"):
                callbacks.append(lgb.early_stopping(rounds, verbose=False))
            else:  # pragma: no cover - legacy API
                from lightgbm import callback  # type: ignore

                callbacks.append(callback.early_stopping(rounds, verbose=False))
        if hasattr(lgb, "log_evaluation"):
            callbacks.append(lgb.log_evaluation(period=0))
        else:  # pragma: no cover - legacy API
            from lightgbm import callback  # type: ignore

            callbacks.append(callback.log_evaluation(period=0))
        return callbacks

    for val_idx in folds:
        train_idx = [i for i in range(len(y)) if i not in val_idx]
        if not train_idx or not val_idx:
            continue
        train_data = lgb.Dataset(X[train_idx], label=y[train_idx], weight=w[train_idx], feature_name=data.feature_names)
        valid_data = lgb.Dataset(X[val_idx], label=y[val_idx], weight=w[val_idx], feature_name=data.feature_names)
        booster = lgb.train(
            params,
            train_data,
            num_boost_round=400,
            valid_sets=[valid_data],
            valid_names=["valid"],
            callbacks=make_callbacks(25),
        )
        best_iter = booster.best_iteration or 400
        best_iterations.append(best_iter)
        preds = booster.predict(X[val_idx], num_iteration=best_iter)
        rmse_scores.append(weighted_rmse(y[val_idx], preds, w[val_idx]))
        mae_scores.append(weighted_mae(y[val_idx], preds, w[val_idx]))

    final_rounds = int(sum(best_iterations) / len(best_iterations)) if best_iterations else 200
    final_rounds = max(final_rounds, 50)
    train_full = lgb.Dataset(X, label=y, weight=w, feature_name=data.feature_names)
    final_model = lgb.train(
        params,
        train_full,
        num_boost_round=final_rounds,
        callbacks=make_callbacks(0),
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "lightgbm_model.txt"
    final_model.save_model(str(model_path))

    importance = final_model.feature_importance(importance_type="gain")
    imp_rows = list(zip(data.feature_names, importance))
    imp_rows.sort(key=lambda item: item[1], reverse=True)
    with (artifact_dir / "feature_importance.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["feature", "gain"])
        writer.writerows(imp_rows)

    preds_full = final_model.predict(X, num_iteration=final_rounds)
    rmse = float(np.mean(rmse_scores)) if rmse_scores else weighted_rmse(y, preds_full, w)
    mae = float(np.mean(mae_scores)) if mae_scores else weighted_mae(y, preds_full, w)
    r2 = weighted_r2(y, preds_full, w)

    return {
        "rmse": round(rmse, 3),
        "mae": round(mae, 3),
        "r2": round(r2, 3) if not math.isnan(r2) else float("nan"),
        "baseline": False,
        "backend": "lightgbm",
        "folds": len(rmse_scores) or 1,
        "best_rounds": final_rounds,
    }


def train_regression_elasticnet(data: RegressionDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    if not SKLEARN_AVAILABLE or np is None:  # pragma: no cover - guarded in caller
        raise RuntimeError("scikit-learn or numpy unavailable")
    if len(data.target) < 5:
        raise RuntimeError("Not enough samples for ElasticNet regression")

    X = np.array(data.matrix, dtype=float)
    y = np.array(data.target, dtype=float)
    w = np.array(data.weights, dtype=float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=5000, random_state=cfg.seed)
    model.fit(X_scaled, y, sample_weight=w)
    preds = model.predict(X_scaled)

    rmse = math.sqrt(mean_squared_error(y, preds, sample_weight=w))
    mae = mean_absolute_error(y, preds, sample_weight=w)
    r2 = r2_score(y, preds, sample_weight=w)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    coeff_path = artifact_dir / "elasticnet_coefficients.json"
    payload = {
        "features": data.feature_names,
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
    }
    coeff_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "rmse": round(rmse, 3),
        "mae": round(mae, 3),
        "r2": round(r2, 3),
        "baseline": False,
        "backend": "elasticnet",
        "folds": 1,
    }


def train_classification_lightgbm(data: ClassificationDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    if lgb is None or np is None:  # pragma: no cover - guarded in caller
        raise RuntimeError("LightGBM or numpy unavailable")
    if len(set(data.labels)) < 2:
        raise RuntimeError("Need both classes for LightGBM classification")

    X = np.array(data.matrix, dtype=float)
    y = np.array(data.labels, dtype=float)
    w = np.array(data.weights, dtype=float)

    folds = make_folds(len(y), min(cfg.k_folds, len(y)), cfg.seed)
    accuracy_scores: List[float] = []
    precision_scores: List[float] = []
    recall_scores: List[float] = []
    f1_scores: List[float] = []
    best_iterations: List[int] = []

    min_leaf = max(5, min(50, max(len(y) // 4, 1)))

    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "min_data_in_leaf": min_leaf,
        "verbosity": -1,
        "seed": cfg.seed,
    }

    def make_callbacks(rounds: int) -> List:
        callbacks = []
        if rounds > 0:
            if hasattr(lgb, "early_stopping"):
                callbacks.append(lgb.early_stopping(rounds, verbose=False))
            else:  # pragma: no cover - legacy API
                from lightgbm import callback  # type: ignore

                callbacks.append(callback.early_stopping(rounds, verbose=False))
        if hasattr(lgb, "log_evaluation"):
            callbacks.append(lgb.log_evaluation(period=0))
        else:  # pragma: no cover
            from lightgbm import callback  # type: ignore

            callbacks.append(callback.log_evaluation(period=0))
        return callbacks

    for val_idx in folds:
        train_idx = [i for i in range(len(y)) if i not in val_idx]
        if not train_idx or not val_idx:
            continue
        train_data = lgb.Dataset(X[train_idx], label=y[train_idx], weight=w[train_idx], feature_name=data.feature_names)
        valid_data = lgb.Dataset(X[val_idx], label=y[val_idx], weight=w[val_idx], feature_name=data.feature_names)
        booster = lgb.train(
            params,
            train_data,
            num_boost_round=300,
            valid_sets=[valid_data],
            valid_names=["valid"],
            callbacks=make_callbacks(20),
        )
        best_iter = booster.best_iteration or 300
        best_iterations.append(best_iter)
        probs = booster.predict(X[val_idx], num_iteration=best_iter)
        preds = [1 if p >= 0.5 else 0 for p in probs]
        metrics = weighted_classification_metrics(y[val_idx], preds, w[val_idx])
        accuracy_scores.append(metrics["accuracy"])
        precision_scores.append(metrics["precision"])
        recall_scores.append(metrics["recall"])
        f1_scores.append(metrics["f1"])

    final_rounds = int(sum(best_iterations) / len(best_iterations)) if best_iterations else 150
    final_rounds = max(final_rounds, 50)
    train_full = lgb.Dataset(X, label=y, weight=w, feature_name=data.feature_names)
    final_model = lgb.train(
        params,
        train_full,
        num_boost_round=final_rounds,
        callbacks=make_callbacks(0),
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    final_model.save_model(str(artifact_dir / "lightgbm_model.txt"))
    importance = final_model.feature_importance(importance_type="gain")
    imp_rows = list(zip(data.feature_names, importance))
    imp_rows.sort(key=lambda item: item[1], reverse=True)
    with (artifact_dir / "feature_importance.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["feature", "gain"])
        writer.writerows(imp_rows)

    probs_full = final_model.predict(X, num_iteration=final_rounds)
    preds_full = [1 if p >= 0.5 else 0 for p in probs_full]
    metrics_full = weighted_classification_metrics(y, preds_full, w)

    return {
        "accuracy": round(metrics_full["accuracy"], 3) if not math.isnan(metrics_full["accuracy"]) else float("nan"),
        "precision": round(metrics_full["precision"], 3) if not math.isnan(metrics_full["precision"]) else float("nan"),
        "recall": round(metrics_full["recall"], 3) if not math.isnan(metrics_full["recall"]) else float("nan"),
        "f1": round(metrics_full["f1"], 3) if not math.isnan(metrics_full["f1"]) else float("nan"),
        "baseline": False,
        "backend": "lightgbm",
        "samples": len(data.labels),
        "best_rounds": final_rounds,
        "thresholds": {"q1": data.thresholds[0], "q3": data.thresholds[1]},
    }


def train_classification_logistic(data: ClassificationDataset, cfg: TrainingConfig, artifact_dir: Path) -> Dict[str, float]:
    if not SKLEARN_AVAILABLE or np is None:  # pragma: no cover - guarded in caller
        raise RuntimeError("scikit-learn or numpy unavailable")
    if len(set(data.labels)) < 2:
        raise RuntimeError("Need both classes for logistic regression")

    X = np.array(data.matrix, dtype=float)
    y = np.array(data.labels, dtype=int)
    w = np.array(data.weights, dtype=float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LogisticRegression(max_iter=5000, random_state=cfg.seed)
    model.fit(X_scaled, y, sample_weight=w)
    preds = model.predict(X_scaled)

    accuracy = accuracy_score(y, preds, sample_weight=w)
    precision = precision_score(y, preds, sample_weight=w, zero_division=0)
    recall = recall_score(y, preds, sample_weight=w, zero_division=0)
    f1 = f1_score(y, preds, sample_weight=w, zero_division=0)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "coefficients": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
        "features": data.feature_names,
    }
    (artifact_dir / "logistic_coefficients.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "baseline": False,
        "backend": "logistic_regression",
        "samples": len(data.labels),
        "thresholds": {"q1": data.thresholds[0], "q3": data.thresholds[1]},
    }


# ---------------------------------------------------------------------------
# Training orchestration


def train_regression(data: RegressionDataset, cfg: TrainingConfig, out_dir: Path) -> Dict[str, float]:
    artifact_dir = out_dir / "regression"

    try:
        if lgb is not None and np is not None:
            return train_regression_lightgbm(data, cfg, artifact_dir)
    except Exception as exc:  # pragma: no cover - only hit when dependencies exist
        warnings.warn(f"LightGBM regression failed ({exc}); falling back to alternative")

    try:
        if SKLEARN_AVAILABLE and np is not None:
            return train_regression_elasticnet(data, cfg, artifact_dir)
    except Exception as exc:  # pragma: no cover
        warnings.warn(f"ElasticNet regression failed ({exc}); using baseline")

    return regression_baseline(data, cfg, artifact_dir)


def train_classification(data: ClassificationDataset, cfg: TrainingConfig, out_dir: Path) -> Dict[str, float]:
    artifact_dir = out_dir / "classification"

    if len(data.labels) >= 2 and len(set(data.labels)) >= 2:
        try:
            if lgb is not None and np is not None:
                return train_classification_lightgbm(data, cfg, artifact_dir)
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"LightGBM classification failed ({exc}); falling back")
        try:
            if SKLEARN_AVAILABLE and np is not None:
                return train_classification_logistic(data, cfg, artifact_dir)
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"Logistic regression failed ({exc}); using baseline")

    return classification_baseline(data, cfg, artifact_dir)


def compute_feature_correlations(data: RegressionDataset) -> List[Tuple[str, float]]:
    weights = data.weights
    total = sum(weights)
    if total == 0:
        return []
    target = data.target
    mean_target = sum(t * w for t, w in zip(target, weights)) / total
    correlations: List[Tuple[str, float]] = []

    for idx, name in enumerate(data.feature_names):
        values = [row[idx] for row in data.matrix]
        mean_feat = sum(v * w for v, w in zip(values, weights)) / total
        cov = sum(w * (t - mean_target) * (v - mean_feat) for t, v, w in zip(target, values, weights))
        var_t = sum(w * (t - mean_target) ** 2 for t, w in zip(target, weights))
        var_f = sum(w * (v - mean_feat) ** 2 for v, w in zip(values, weights))
        if var_t <= 0 or var_f <= 0:
            continue
        correlations.append((name, cov / math.sqrt(var_t * var_f)))

    correlations.sort(key=lambda item: abs(item[1]), reverse=True)
    return correlations[:25]


def ensure_output_dir(base: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_dir = base / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def summarize(
    cfg: TrainingConfig,
    regression_metrics: Optional[Dict[str, float]],
    classification_metrics: Optional[Dict[str, float]],
    correlations: List[Tuple[str, float]],
    out_dir: Path,
) -> None:
    notes: List[str] = []
    if regression_metrics and regression_metrics.get("baseline"):
        notes.append("Regression fallback baseline used (install LightGBM/ElasticNet for full modelling).")
    if classification_metrics and classification_metrics.get("baseline"):
        notes.append("Classification fallback baseline used (install LightGBM/sklearn for advanced modelling).")
    if not notes:
        notes.append("Advanced models trained successfully; SHAP pipeline can now consume saved models.")

    summary = {
        "config": {
            "features_path": str(cfg.features_path),
            "min_hands": cfg.min_hands,
            "tasks": list(cfg.tasks),
            "weight_strategy": cfg.weight_strategy,
            "k_folds": cfg.k_folds,
            "seed": cfg.seed,
        },
        "metrics": {
            "regression": regression_metrics,
            "classification": classification_metrics,
        },
        "top_correlations": [
            {"feature": key, "pearson": round(value, 4)} for key, value in correlations
        ],
        "notes": notes,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point


def main(argv: Optional[Sequence[str]] = None) -> None:
    cfg = parse_args(argv)
    raw_rows = load_features(cfg.features_path)
    filtered_rows = filter_rows(raw_rows, cfg.min_hands)
    if not filtered_rows:
        raise SystemExit("No players met the minimum hand count threshold.")

    regression_data = build_regression_dataset(filtered_rows, cfg)
    classification_data = build_classification_dataset(regression_data)

    run_dir = ensure_output_dir(cfg.out_dir)

    regression_metrics: Optional[Dict[str, float]] = None
    classification_metrics: Optional[Dict[str, float]] = None

    if "regression" in cfg.tasks:
        regression_metrics = train_regression(regression_data, cfg, run_dir)

    if "classification" in cfg.tasks:
        classification_metrics = train_classification(classification_data, cfg, run_dir)

    correlations = compute_feature_correlations(regression_data)
    summarize(cfg, regression_metrics, classification_metrics, correlations, run_dir)
    print(f"Saved artefacts to {run_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
