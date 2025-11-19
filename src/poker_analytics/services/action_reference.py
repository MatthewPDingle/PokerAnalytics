"""Expose cached action quick-reference recommendations.

This module serves a lightweight wrapper around precomputed recommendation
payloads stored under ``var/cache``. The heavy lifting (deriving bluff/value
recommendations from the response matrices) is performed offline and the
results are serialized as JSON:

    action_recommendations_<stake>.json

The current implementation intentionally keeps the contract minimal so the
generation logic can evolve independently of the API surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from poker_analytics.config import build_data_paths
from poker_analytics.data.stakes import StakePolicy


CACHE_BASENAME = "action_recommendations"


def _candidate_paths(cache_dir: Path, filename: str) -> Iterable[Path]:
    """Yield possible cache locations ordered by preference.

    The primary location is the root cache directory. If an
    ``active_data_source.json`` file is present, we then prefer the matching
    subdirectory (e.g. ``drivehud`` or ``pokerstars_nl10``). Finally, every
    direct subdirectory is considered as a fallback.
    """

    yield cache_dir / filename

    active_source_path = cache_dir / "active_data_source.json"
    if active_source_path.exists():
        try:
            active_payload = json.loads(active_source_path.read_text(encoding="utf-8"))
            active_key = active_payload.get("key")
            if isinstance(active_key, str) and active_key:
                yield cache_dir / active_key / filename
        except (OSError, json.JSONDecodeError):
            # Treat a malformed active-source file as if it were absent.
            pass

    try:
        for entry in cache_dir.iterdir():
            if not entry.is_dir():
                continue
            candidate = entry / filename
            if candidate.exists():
                yield candidate
    except OSError:
        # If we cannot iterate the directory, we fall back to the primary path.
        return


def _load_first_existing(paths: Iterable[Path]) -> Dict[str, Any] | None:
    for path in paths:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and "rows" in payload:
            return payload
    return None


def load_action_reference(source: str | None = None) -> Dict[str, Any]:
    """Return cached recommendations for the active stake policy.

    The returned payload mirrors the on-disk JSON structure and exposes two
    keys:

    - ``version``: integer payload version for forwards compatibility.
    - ``rows``: list of recommendation records.

    If no cache is available, an empty payload is returned instead of raising
    so the frontend can render a graceful "no data" message.
    """

    stake_policy = StakePolicy.from_environment()
    data_paths = build_data_paths()

    filename = f"{CACHE_BASENAME}_{stake_policy.cache_token()}.json"

    if source:
        source_key = source.strip()
        candidates: List[Path] = [
            data_paths.cache_dir / source_key / filename,
            data_paths.cache_dir / filename,
        ]
    else:
        candidates = list(_candidate_paths(data_paths.cache_dir, filename))

    payload = _load_first_existing(candidates)
    if payload is not None:
        return payload

    # Fallback: empty payload with a version marker for robustness.
    return {"version": 1, "rows": []}


__all__ = ["load_action_reference"]
