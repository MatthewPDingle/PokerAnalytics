"""Thin SQLite helpers for read-only workloads."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _readonly_uri(db_path: Path) -> str:
    resolved = db_path.resolve()
    uri = resolved.as_uri()
    suffix = "mode=ro&immutable=1"
    return f"{uri}?{suffix}" if "?" not in uri else f"{uri}&{suffix}"


@contextmanager
def connect_readonly(db_path: Path, timeout: float = 60.0) -> Iterator[sqlite3.Connection]:
    """Open an SQLite database for read-only access.

    The helper mirrors legacy behaviour used in the notebooks: we prefer using
    the SQLite URI with ``mode=ro`` and ``immutable=1`` to avoid write locks.
    On network-mounted paths (notably WSL shares) this may still raise
    ``OperationalError`` due to locking. In that case we fall back to copying
    the database to a temporary file and opening the copy.
    """

    tmp_copy: Path | None = None
    try:
        conn = sqlite3.connect(
            _readonly_uri(db_path),
            uri=True,
            timeout=timeout,
            check_same_thread=False,
        )
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "locked" not in message and "busy" not in message:
            raise
        fd, tmp_name = tempfile.mkstemp(suffix=".db", prefix=f"{db_path.stem}-copy-")
        os.close(fd)
        tmp_copy = Path(tmp_name)
        shutil.copy2(db_path, tmp_copy)
        conn = sqlite3.connect(tmp_copy, timeout=timeout, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()
        if tmp_copy is not None:
            try:
                tmp_copy.unlink()
            except OSError:
                pass


__all__ = ["connect_readonly"]
