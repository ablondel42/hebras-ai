import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from core.command_memory import CommandMemoryStore

logger = logging.getLogger(__name__)

# Global memory store instance (lazy initialized)
_memory_store: CommandMemoryStore | None = None


def get_memory_store() -> CommandMemoryStore:
    """Lazy initialize global CommandMemoryStore instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = CommandMemoryStore()
    return _memory_store


@dataclass
class ExecutionResult:
    """Result of a safe command execution."""
    stdout: str
    stderr: str
    returncode: int
    duration_ms: int
    was_mitigated: bool = False
    applied_rule_description: str | None = None


async def safe_run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    override_stdin_devnull: bool | None = None,
) -> ExecutionResult:
    """Execute a command line safely with anti-hang memory interception.

    Args:
        cmd: List of command arguments.
        cwd: Working directory path.
        timeout: Maximum execution timeout in seconds.
        env: Additional environment variables.
        override_stdin_devnull: If True, forces stdin to DEVNULL regardless of rules.

    Returns:
        ExecutionResult containing stdout, stderr, returncode, and mitigation details.
    """
    cmd_str = " ".join(cmd)
    memory_store = get_memory_store()
    rule = memory_store.match(cmd_str)

    # Defaults: close stdin if overridden or matched by rule or default True for non-interactive safe execution
    close_stdin = override_stdin_devnull is not False
    exec_env = dict(os.environ)
    if env:
        exec_env.update(env)

    exec_cmd = list(cmd)
    was_mitigated = False
    rule_desc = None

    if rule:
        was_mitigated = True
        rule_desc = rule.description
        logger.info(f"Anti-hang interceptor matched '{cmd_str}': {rule.description}")

        if rule.close_stdin:
            close_stdin = True

        if rule.env_overrides:
            exec_env.update(rule.env_overrides)

        if rule.added_args:
            exec_cmd.extend(rule.added_args)

        timeout = min(timeout, rule.timeout_seconds)

    stdin_arg = asyncio.subprocess.DEVNULL if close_stdin else asyncio.subprocess.PIPE

    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *exec_cmd,
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

        # Detect permission auto-denial / unpromptable tool blockage signature
        if "auto-denied" in stdout_text.lower() or "auto-denied" in stderr_text.lower():
            logger.warning(f"Anti-hang memory: Permission auto-denial detected for '{cmd_str}'")
            memory_store.learn_hang(
                cmd_str,
                reason="Tool permission auto-denied in headless mode",
                suggested_mitigation="close_stdin",
            )

        return ExecutionResult(
            stdout=stdout_text,
            stderr=stderr_text,
            returncode=proc.returncode or 0,
            duration_ms=duration_ms,
            was_mitigated=was_mitigated,
            applied_rule_description=rule_desc,
        )

    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Anti-hang detector: Command timed out after {timeout}s: '{cmd_str}'")

        # Auto-learn the hang and save to global memory store (~/.gemini/command_memory.json)
        learned_rule = memory_store.learn_hang(
            cmd_str,
            reason=f"Timed out after {timeout}s waiting for completion/stdin input",
            suggested_mitigation="close_stdin",
        )

        try:
            proc.kill()
            await proc.wait()
        except Exception as e:
            logger.warning(f"Failed to kill timed out process: {e}")

        return ExecutionResult(
            stdout="",
            stderr=f"Command execution timed out after {timeout}s (learned global rule: {learned_rule.pattern})",
            returncode=124,
            duration_ms=duration_ms,
            was_mitigated=True,
            applied_rule_description=f"Auto-learned hang rule for pattern '{learned_rule.pattern}'",
        )
