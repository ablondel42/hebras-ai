"""Shared test fixtures for hebras-ai."""
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.session_manager import SessionManager


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create an async HTTP test client with lifespan initialized.

    Manually sets up the SessionManager on app.state so that
    endpoints relying on it work correctly in tests.
    """
    sm = SessionManager()
    await sm.start()
    app.state.session_manager = sm
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    finally:
        await sm.stop()

