"""Tests for InteractiveSession lifecycle with mocked pexpect."""
import asyncio
from unittest.mock import MagicMock, patch
import pytest
from core.agy_interactive import InteractiveSession, InteractiveSessionError


class TestInteractiveSession:
    def test_default_config(self):
        session = InteractiveSession(agent="read")
        assert session.agent == "read"
        assert session.auto_approve is False
        assert not session.is_alive()
        assert session.conversation_id is not None

    @patch("core.agy_interactive.pexpect")
    async def test_start_spawns_process(self, mock_pexpect):
        mock_child = MagicMock()
        mock_child.isalive.return_value = True
        mock_pexpect.spawn.return_value = mock_child

        session = InteractiveSession(agent="read")
        await session.start()

        assert mock_pexpect.spawn.called
        assert session.is_alive()

    async def test_send_without_start_raises(self):
        session = InteractiveSession(agent="read")
        with pytest.raises(InteractiveSessionError, match="not alive"):
            await session.send_message("hello")

    @patch("core.agy_interactive.pexpect")
    async def test_close_terminates(self, mock_pexpect):
        mock_child = MagicMock()
        mock_child.isalive.return_value = True
        mock_pexpect.spawn.return_value = mock_child

        session = InteractiveSession(agent="read")
        await session.start()
        await session.close()

        mock_child.close.assert_called_once_with(force=True)
        assert not session.is_alive()
