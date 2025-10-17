"""Primary API routes."""

from __future__ import annotations

from fastapi import APIRouter

from poker_analytics.services.flop_loader import load_flop_bet_summary
from poker_analytics.services.flop_response_matrix import load_flop_response_matrix

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health", summary="Service health check")
async def health() -> dict[str, str]:
    """Return a simple health payload for uptime checks."""

    return {"status": "ok"}


@router.get("/metadata", summary="Metadata about the service")
async def metadata() -> dict[str, str]:
    """Expose lightweight build metadata for the frontend landing page."""

    return {
        "service": "Poker Analytics",
        "version": "0.1.0",
        "description": "Analytics and visualization backend for poker hand histories.",
    }


@router.get("/flop/summary", summary="Flop bet-size summary")
async def flop_summary() -> dict:
    return load_flop_bet_summary()


@router.get("/flop/response-matrix", summary="Flop bet response matrix")
async def flop_response_matrix() -> dict:
    return load_flop_response_matrix()
