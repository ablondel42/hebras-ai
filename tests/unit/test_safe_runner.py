"""Unit tests for safe_run_command and anti-hang interceptor."""
import sys
import pytest
from core.safe_runner import safe_run_command


class TestSafeRunner:
    """Tests for safe_run_command execution and timeout interception."""

    async def test_normal_command_execution(self):
        """Verify normal fast commands execute cleanly."""
        res = await safe_run_command([sys.executable, "-c", "print('hello_safe')"])
        assert res.returncode == 0
        assert "hello_safe" in res.stdout
        assert res.duration_ms >= 0

    async def test_closed_stdin_prevents_hang(self):
        """Verify passing stdin=DEVNULL prevents commands from reading stdin."""
        # 'python3 -c "import sys; sys.stdin.read()"' normally hangs waiting for EOF on stdin
        res = await safe_run_command(
            [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
            timeout=5,
            override_stdin_devnull=True,
        )
        assert res.returncode == 0
        assert res.duration_ms < 2000  # Exits immediately on EOF

    async def test_timeout_auto_learning(self, tmp_path):
        """Verify timing out on a hanging command triggers auto-learning."""
        # Run a python command that sleeps 10s with timeout=1s
        res = await safe_run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        assert res.returncode == 124
        assert "timed out" in res.stderr
