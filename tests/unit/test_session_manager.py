"""Tests for SessionManager."""
import pytest

from backend.session_manager import SessionManager, SessionNotFound, SessionPoolFull


@pytest.fixture
def manager():
    """Create a test SessionManager with small pool."""
    return SessionManager(max_sessions=2, idle_timeout=5)


class TestSessionManager:
    """Tests for the SessionManager pool."""

    async def test_create_session(self, manager):
        """Verify session creation."""
        session = await manager.create_session(agent="default")
        assert session.agent == "default"
        assert session.session_id is not None

    async def test_create_session_with_workspace(self, manager):
        """Verify session creation with workspace."""
        session = await manager.create_session(agent="default", workspace="/tmp/test")
        assert session.workspace == "/tmp/test"

    async def test_create_session_with_model(self, manager):
        """Verify session creation with custom model."""
        session = await manager.create_session(agent="coder", model="Claude 3.7 Sonnet")
        assert session.agent == "coder"
        assert session.model == "Claude 3.7 Sonnet"

    async def test_pool_full(self, manager):
        """Verify SessionPoolFull is raised when pool is at capacity."""
        await manager.create_session(agent="default")
        await manager.create_session(agent="test")
        with pytest.raises(SessionPoolFull):
            await manager.create_session(agent="default")

    async def test_get_session(self, manager):
        """Verify session retrieval by ID."""
        session = await manager.create_session(agent="default")
        retrieved = await manager.get_session(session.session_id)
        assert retrieved.session_id == session.session_id
        assert retrieved.agent == "default"

    async def test_get_nonexistent_session(self, manager):
        """Verify SessionNotFound for nonexistent ID."""
        with pytest.raises(SessionNotFound):
            await manager.get_session("nonexistent-id")

    async def test_delete_session(self, manager):
        """Verify session deletion."""
        session = await manager.create_session(agent="default")
        await manager.delete_session(session.session_id)
        with pytest.raises(SessionNotFound):
            await manager.get_session(session.session_id)

    async def test_delete_nonexistent_session(self, manager):
        """Verify deleting nonexistent session doesn't raise."""
        await manager.delete_session("nonexistent-id")  # Should not raise

    async def test_list_sessions(self, manager):
        """Verify listing all sessions."""
        s1 = await manager.create_session(agent="default")
        s2 = await manager.create_session(agent="test")
        sessions = await manager.list_sessions()
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids

    async def test_session_expiry(self, manager):
        """Verify expired sessions are evicted."""
        manager._idle_timeout = 0  # Expire immediately
        session = await manager.create_session(agent="default")
        with pytest.raises(SessionNotFound):
            await manager.get_session(session.session_id)

    async def test_pool_frees_after_delete(self, manager):
        """Verify pool space is freed after deletion."""
        s1 = await manager.create_session(agent="default")
        await manager.create_session(agent="test")
        await manager.delete_session(s1.session_id)
        # Should now have room for a new session
        s3 = await manager.create_session(agent="default")
        assert s3.session_id != s1.session_id
