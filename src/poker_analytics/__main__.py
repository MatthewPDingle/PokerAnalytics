"""Executable entry point for running the FastAPI app."""

from __future__ import annotations

import uvicorn

from poker_analytics.app import app


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
