"""Helpers for enumerating available analytics data sources.

Data sources currently correspond to subdirectories under the cache root
(``var/cache/<source>``) such as ``drivehud`` or ``pokerstars_nl10``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from poker_analytics.config import build_data_paths


def _friendly_label(key: str) -> str:
  tokens = key.replace("-", "_").split("_")
  pieces: List[str] = []
  for token in tokens:
    token = token.strip()
    if not token:
      continue
    if any(ch.isdigit() for ch in token):
      pieces.append(token.upper())
    else:
      pieces.append(token.capitalize())
  return " ".join(pieces) if pieces else key


def list_data_sources() -> Dict[str, Any]:
  """Return available data sources and the active key (if any)."""

  data_paths = build_data_paths()
  cache_dir = data_paths.cache_dir

  active_key: str | None = None
  active_path = cache_dir / "active_data_source.json"
  if active_path.exists():
    try:
      payload = json.loads(active_path.read_text(encoding="utf-8"))
      key = payload.get("key")
      if isinstance(key, str) and key:
        active_key = key
    except (OSError, json.JSONDecodeError):
      active_key = None

  sources: List[Dict[str, str]] = []
  try:
    for entry in sorted(cache_dir.iterdir(), key=lambda p: p.name):
      if not entry.is_dir():
        continue
      key = entry.name
      sources.append({"key": key, "label": _friendly_label(key)})
  except OSError:
    sources = []

  return {"sources": sources, "active": active_key}


__all__ = ["list_data_sources"]

