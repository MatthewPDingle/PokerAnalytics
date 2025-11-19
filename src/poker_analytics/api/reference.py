"""API routes for quick-reference helpers."""

from __future__ import annotations

from fastapi import APIRouter, Query

from poker_analytics.services.action_reference import load_action_reference
from poker_analytics.services.data_sources import list_data_sources

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/action-reference", summary="Action Quick Reference data")
async def action_reference(source: str | None = Query(default=None)) -> dict:
    """Return cached action recommendations used by the quick-reference page.

    When a ``source`` key is provided, recommendations are loaded from the
    matching cache subdirectory under ``var/cache/<source>``. Otherwise, the
    active data source (or default cache) is used.
    """

    return load_action_reference(source=source)


@router.get("/data-sources", summary="Available analytics data sources")
async def data_sources() -> dict:
    """Return the known data sources and active key."""

    return list_data_sources()


__all__ = ["router"]

