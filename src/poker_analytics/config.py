"""Application configuration helpers.

Centralizes filesystem paths and environment-driven overrides used across the
analytics stack. This module intentionally avoids third-party dependencies so
it can be imported before the main dependency graph is installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "var" / "cache"
DEFAULT_ALLOWED_BIG_BLINDS = (0.10,)

# Ordered by preference: Windows path, WSL mount, repo-local copy.
DEFAULT_DRIVEHUD_CANDIDATES = (
    Path(r"T:\\Dev\\ignition\\drivehud\\drivehud.db"),
    Path("/mnt/t/Dev/ignition/drivehud/drivehud.db"),
    REPO_ROOT / "drivehud" / "drivehud.db",
)


@dataclass(frozen=True)
class DataPaths:
    """Resolved filesystem locations for key data assets."""

    drivehud_db: Path
    cache_dir: Path

    def ensure_cache_dir(self) -> None:
        """Create the cache directory if it does not exist."""

        self.cache_dir.mkdir(parents=True, exist_ok=True)


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for candidate in paths:
        if candidate.exists():
            return candidate
    return None


def resolve_drivehud_path() -> Path:
    """Return the expected location of `drivehud.db`.

    An explicit override can be supplied with the `DRIVEHUD_DB_PATH`
    environment variable. Otherwise we search the default candidates.
    """

    override = os.getenv("DRIVEHUD_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()

    found = _first_existing(DEFAULT_DRIVEHUD_CANDIDATES)
    if found:
        return found

    # Fall back to the last candidate even if missing so downstream code can
    # decide how to handle the absence.
    return DEFAULT_DRIVEHUD_CANDIDATES[-1]


def resolve_cache_dir() -> Path:
    """Return the cache directory location with env override support."""

    override = os.getenv("POKER_ANALYTICS_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_CACHE_DIR


def resolve_allowed_big_blinds() -> tuple[float, ...]:
    """Return the set of big blind stakes the application should include.

    The ``POKER_ANALYTICS_ALLOWED_BIG_BLINDS`` environment variable accepts a
    comma- or semicolon-delimited list of numeric big blind amounts. Providing
    ``*`` disables filtering and includes every available stake.
    """

    raw = os.getenv("POKER_ANALYTICS_ALLOWED_BIG_BLINDS")
    if raw is None or not raw.strip():
        return DEFAULT_ALLOWED_BIG_BLINDS

    tokens = [token.strip() for token in raw.replace(";", ",").split(",") if token.strip()]
    if not tokens:
        return DEFAULT_ALLOWED_BIG_BLINDS

    if any(token == "*" for token in tokens):
        return ()

    values: list[float] = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError:
            continue

    return tuple(values) if values else DEFAULT_ALLOWED_BIG_BLINDS


def build_data_paths() -> DataPaths:
    """Construct a `DataPaths` instance using resolution helpers."""

    return DataPaths(
        drivehud_db=resolve_drivehud_path(),
        cache_dir=resolve_cache_dir(),
    )


__all__ = [
    "DataPaths",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_DRIVEHUD_CANDIDATES",
    "DEFAULT_ALLOWED_BIG_BLINDS",
    "build_data_paths",
    "resolve_cache_dir",
    "resolve_drivehud_path",
    "resolve_allowed_big_blinds",
]
