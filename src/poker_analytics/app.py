"""FastAPI application factory for the Poker Analytics backend."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from poker_analytics.api import core_router, performance_router, preflop_router, reference_router
from poker_analytics.config import REPO_ROOT
from poker_analytics.services.cache_refresh import (
    refresh_flop_caches,
    refresh_turn_caches,
    refresh_river_caches,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Poker Analytics", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(core_router)
    app.include_router(preflop_router)
    app.include_router(performance_router)
    app.include_router(reference_router)

    def _warm_caches() -> None:
        refresh_flop_caches()
        refresh_turn_caches()
        refresh_river_caches()

    @app.on_event("startup")
    async def _refresh_flop_caches() -> None:
        try:
            await asyncio.to_thread(_warm_caches)
        except Exception:  # pragma: no cover - startup resilience
            # Avoid failing app startup if cache warm-up has issues.
            pass

    dist_dir = REPO_ROOT / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/static", StaticFiles(directory=dist_dir, html=True), name="static")

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def serve_index() -> str:  # pragma: no cover - runtime only when dist exists
            index_path = dist_dir / "index.html"
            return index_path.read_text(encoding="utf-8")

    return app


app = create_app()


__all__ = ["app", "create_app"]
