"""Performance-related API routes."""

from __future__ import annotations

from fastapi import APIRouter

from poker_analytics.services.opponent_performance import get_opponent_count_performance

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/opponent-count", summary="Hero performance by opponent count and timeline")
async def performance_by_opponent_count() -> dict[str, object]:
    """Return hero winrate and preflop stats bucketed by number of opponents."""

    return get_opponent_count_performance()


__all__ = ["router"]
