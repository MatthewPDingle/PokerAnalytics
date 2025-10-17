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
    """Open an SQLite database for read-only workloads without holding persistent locks.

    On Windows the repository often lives under ``\\\\wsl$``. SQLite's default locking
    does not play well with that UNC path and raises ``database is locked`` even for
    read-only readers. Opening the file via the URI ``mode=ro`` + ``immutable=1`` avoids
    write locks; if the share still reports the file as busy we fall back to copying the
    database to a temporary location on the local filesystem.
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
        conn = sqlite3.connect(tmp_name, timeout=timeout, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()
        if tmp_copy is not None:
            try:
                tmp_copy.unlink()
            except OSError:
                pass
