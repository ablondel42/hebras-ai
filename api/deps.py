"""FastAPI dependency injection helpers."""
from fastapi import Request

from core.session_manager import SessionManager


def get_session_manager(request: Request) -> SessionManager:
    """Get the SessionManager from app state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The SessionManager instance.
    """
    return request.app.state.session_manager
