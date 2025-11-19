"""API routers for the Poker Analytics backend."""

from .main import router as core_router
from .performance import router as performance_router
from .preflop import router as preflop_router
from .reference import router as reference_router

__all__ = ["core_router", "preflop_router", "performance_router", "reference_router"]
