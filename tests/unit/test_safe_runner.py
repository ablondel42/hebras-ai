"""Unit tests for safe_run_command process execution engine."""
import sys

from backend.safe_runner import safe_run_command


class TestSafeRunner:
    """Tests for safe_run_command execution and timeout handling."""

    async def test_normal_command_execution(self):
        """Verify normal fast commands execute cleanly."""
        res = await safe_run_command([sys.executable, "-c", "print('hello_safe')"])
        assert res.returncode == 0
        assert "hello_safe" in res.stdout
        assert res.duration_ms >= 0

    async def test_closed_stdin_prevents_hang(self):
        """Verify passing stdin=DEVNULL prevents commands from reading stdin."""
        res = await safe_run_command(
            [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
            timeout=5,
            override_stdin_devnull=True,
        )
        assert res.returncode == 0
        assert res.duration_ms < 2000

    async def test_timeout_handling(self):
        """Verify timing out on a command kills process and returns returncode 124."""
        res = await safe_run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        assert res.returncode == 124
        assert "timed out" in res.stderr
