"""Tests for InteractiveSession lifecycle with mocked pexpect."""
from unittest.mock import MagicMock, patch

import pytest

from backend.agy_interactive import InteractiveSession, InteractiveSessionError


class TestInteractiveSession:
    def test_default_config(self, tmp_path):
        session = InteractiveSession(agent="default", workspace=str(tmp_path))
        assert session.agent == "default"
        assert session.auto_approve is False
        assert not session.is_alive()
        assert session.conversation_id is not None

    @patch("backend.agy_interactive.pexpect")
    async def test_start_spawns_process(self, mock_pexpect, tmp_path):
        mock_child = MagicMock()
        mock_child.isalive.return_value = True
        mock_pexpect.spawn.return_value = mock_child

        session = InteractiveSession(agent="default", workspace=str(tmp_path))
        await session.start()

        assert mock_pexpect.spawn.called
        assert session.is_alive()
        assert session.pty_dump_file_path.exists()
        await session.close()

    async def test_send_without_start_raises(self, tmp_path):
        session = InteractiveSession(agent="default", workspace=str(tmp_path))
        with pytest.raises(InteractiveSessionError, match="not alive"):
            await session.send_message("hello")

    @patch("backend.agy_interactive.pexpect")
    async def test_close_terminates(self, mock_pexpect, tmp_path):
        mock_child = MagicMock()
        mock_child.isalive.return_value = True
        mock_pexpect.spawn.return_value = mock_child

        session = InteractiveSession(agent="default", workspace=str(tmp_path))
        await session.start()
        await session.close()

        mock_child.close.assert_called_once_with(force=True)
        assert not session.is_alive()

    @patch("backend.agy_interactive.pexpect")
    async def test_drain_buffer_flushes_file(self, mock_pexpect, tmp_path):
        mock_child = MagicMock()
        mock_child.isalive.return_value = True
        mock_child.read_nonblocking.return_value = "streamed chunk"
        mock_pexpect.spawn.return_value = mock_child

        session = InteractiveSession(agent="default", workspace=str(tmp_path))
        await session.start()

        assert session._dump_file is not None
        session._drain_pty_buffer()
        mock_child.read_nonblocking.assert_called()

        await session.close()
        assert session._dump_file is None
