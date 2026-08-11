from fastapi import HTTPException, Request

from core.session_manager import SessionManager


def get_session_manager(request: Request) -> SessionManager:
    """Get the SessionManager from app state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The SessionManager instance.
    """
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="SessionManager not initialized")
    return manager
