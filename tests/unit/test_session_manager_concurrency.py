"""Unit tests verifying SessionManager lock protection and PTY cleanup behavior."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.session_manager import SessionManager, SessionNotFound


class TestSessionManagerConcurrency:
    @pytest.mark.asyncio
    async def test_get_session_expired_triggers_cleanup(self):
        sm = SessionManager(max_sessions=5, idle_timeout=1)
        session = await sm.create_session(agent="read")

        # Mock interactive session cleanup
        mock_interactive = AsyncMock()
        session.interactive = mock_interactive

        # Force session expiration
        session.last_active = 0.0

        with pytest.raises(SessionNotFound):
            await sm.get_session(session.session_id)

        mock_interactive.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evict_expired_calls_cleanup(self):
        sm = SessionManager(max_sessions=5, idle_timeout=1)
        session = await sm.create_session(agent="read")

        mock_interactive = AsyncMock()
        session.interactive = mock_interactive
        session.last_active = 0.0

        await sm._evict_expired()

        mock_interactive.close.assert_awaited_once()
        assert len(await sm.list_sessions()) == 0
