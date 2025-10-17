"""FastAPI application factory for the Poker Analytics backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from poker_analytics.api import core_router, performance_router, preflop_router
from poker_analytics.config import REPO_ROOT


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
