"""Safe command execution engine with non-interactive stdin and timeout enforcement."""
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a safe command execution."""

    stdout: str
    stderr: str
    returncode: int
    duration_ms: int


async def safe_run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    override_stdin_devnull: bool | None = None,
) -> ExecutionResult:
    """Execute a command line safely with stdin protection and timeout enforcement.

    Args:
        cmd: List of command arguments.
        cwd: Working directory path.
        timeout: Maximum execution timeout in seconds.
        env: Additional environment variables.
        override_stdin_devnull: If True, forces stdin to DEVNULL.

    Returns:
        ExecutionResult containing stdout, stderr, returncode, and duration_ms.
    """
    cmd_str = " ".join(cmd)
    close_stdin = override_stdin_devnull is not False
    exec_env = dict(os.environ)
    if env:
        exec_env.update(env)

    stdin_arg = asyncio.subprocess.DEVNULL if close_stdin else asyncio.subprocess.PIPE
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=stdin_arg,
            cwd=Path(cwd).expanduser().resolve() if cwd else None,
            env=exec_env,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        return ExecutionResult(
            stdout=stdout_text,
            stderr=stderr_text,
            returncode=proc.returncode or 0,
            duration_ms=duration_ms,
        )

    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Command timed out after {timeout}s: '{cmd_str}'")

        try:
            proc.kill()
            await proc.wait()
        except Exception as e:
            logger.warning(f"Failed to kill timed out process: {e}")

        return ExecutionResult(
            stdout="",
            stderr=f"Command execution timed out after {timeout}s",
            returncode=124,
            duration_ms=duration_ms,
        )
