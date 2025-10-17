"""Preflop-related API routes."""

from __future__ import annotations

from fastapi import APIRouter

from poker_analytics.services.preflop_response_curves import get_response_curve_payload
from poker_analytics.services.preflop_shove import get_equity_payload, get_shove_range_payload

router = APIRouter(prefix="/api/preflop", tags=["preflop"])


@router.get("/shove/ranges", summary="Shove range distributions")
async def shove_ranges() -> list[dict]:
    """Return 13×13 grids describing shove frequencies for canonical categories."""

    return get_shove_range_payload()


@router.get("/shove/equity", summary="Shove equity heatmaps")
async def shove_equity() -> list[dict]:
    """Return simulated equity and EV heatmaps for shove scenarios."""

    return get_equity_payload()


@router.get("/response-curves", summary="Preflop sizing response curves")
async def preflop_response_curves() -> list[dict]:
    """Return fold/call/raise frequencies across bet-sizing choices."""

    return get_response_curve_payload()


__all__ = ["router"]
