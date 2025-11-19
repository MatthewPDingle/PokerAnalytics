"""Primary API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from poker_analytics.services.flop_hand_matrix import load_flop_hand_matrix
from poker_analytics.services.flop_loader import load_flop_bet_summary
from poker_analytics.services.flop_responder_hand_matrix import load_flop_responder_hand_matrix
from poker_analytics.services.flop_response_matrix import (
    load_flop_pot_contribution,
    load_flop_response_matrix,
)
from poker_analytics.services.turn_hand_matrix import load_turn_hand_matrix
from poker_analytics.services.turn_responder_hand_matrix import load_turn_responder_hand_matrix
from poker_analytics.services.turn_response_matrix import (
    load_turn_pot_contribution,
    load_turn_response_matrix,
)
from poker_analytics.services.river_hand_matrix import load_river_hand_matrix
from poker_analytics.services.river_responder_hand_matrix import load_river_responder_hand_matrix
from poker_analytics.services.river_response_matrix import (
    load_river_pot_contribution,
    load_river_response_matrix,
)
from poker_analytics.services.line_explorer import load_line_explorer
from poker_analytics.services.line_query import query_line
from poker_analytics.services.line_responder_hand_matrix import load_line_responder_hand_matrix

router = APIRouter(prefix="/api", tags=["core"])


def _normalise_source(source: str | None) -> str | None:
    """Map canonical DriveHUD source to default behaviour.

    The backend treats the default DriveHUD / Ignition data source as the
    canonical dataset, which historically did not require an explicit
    ``source`` key. When the frontend passes ``source=drivehud`` we normalise
    this back to ``None`` so existing DB-backed loaders continue to work and
    cache lookups behave as before.
    """

    if source is None:
        return None
    cleaned = source.strip().lower()
    if not cleaned or cleaned == "drivehud":
        return None
    return source


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
async def flop_response_matrix(source: str | None = Query(default=None)) -> dict:
    return load_flop_response_matrix(source=_normalise_source(source))


@router.get("/flop/pot-contribution", summary="Average pot contribution by bet size")
async def flop_pot_contribution(source: str | None = Query(default=None)) -> dict:
    return load_flop_pot_contribution(source=_normalise_source(source))


@router.get("/flop/hand-types", summary="Hero flop hand categories by bet size")
async def flop_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_flop_hand_matrix(source=_normalise_source(source))


@router.get("/flop/responder-hand-matrix", summary="Responder flop hand categories by bet size")
async def flop_responder_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_flop_responder_hand_matrix(source=_normalise_source(source))


@router.get("/turn/response-matrix", summary="Turn bet response matrix")
async def turn_response_matrix(source: str | None = Query(default=None)) -> dict:
    return load_turn_response_matrix(source=_normalise_source(source))


@router.get("/turn/pot-contribution", summary="Average turn pot contribution by bet size")
async def turn_pot_contribution(source: str | None = Query(default=None)) -> dict:
    return load_turn_pot_contribution(source=_normalise_source(source))


@router.get("/turn/hand-types", summary="Hero turn hand categories by bet size")
async def turn_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_turn_hand_matrix(source=_normalise_source(source))


@router.get("/turn/responder-hand-matrix", summary="Responder turn hand categories by bet size")
async def turn_responder_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_turn_responder_hand_matrix(source=_normalise_source(source))


@router.get("/river/response-matrix", summary="River bet response matrix")
async def river_response_matrix(source: str | None = Query(default=None)) -> dict:
    return load_river_response_matrix(source=_normalise_source(source))


@router.get("/river/pot-contribution", summary="Average river pot contribution by bet size")
async def river_pot_contribution(source: str | None = Query(default=None)) -> dict:
    return load_river_pot_contribution(source=_normalise_source(source))


@router.get("/river/hand-types", summary="Hero river hand categories by bet size")
async def river_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_river_hand_matrix(source=_normalise_source(source))


@router.get("/river/responder-hand-matrix", summary="Responder river hand categories by bet size")
async def river_responder_hand_types(source: str | None = Query(default=None)) -> dict:
    return load_river_responder_hand_matrix(source=_normalise_source(source))


@router.get("/lines/explorer", summary="Multi-street line explorer aggregates")
async def line_explorer(source: str | None = Query(default=None)) -> dict:
    return load_line_explorer(source=_normalise_source(source))


@router.get("/lines/responder-hand-matrix", summary="Responder hand breakdown for line explorer")
async def line_responder_hand_matrix(source: str | None = Query(default=None)) -> dict:
    return load_line_responder_hand_matrix(source=_normalise_source(source))


@router.post("/lines/query", summary="Dynamic line query endpoint")
async def line_query_endpoint(payload: dict, source: str | None = Query(default=None)) -> dict:
    try:
        return query_line(payload, source=_normalise_source(source))
    except ValueError as exc:  # surfacing schema errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
