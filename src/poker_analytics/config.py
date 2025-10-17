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
    "build_data_paths",
    "resolve_cache_dir",
    "resolve_drivehud_path",
]
