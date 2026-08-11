"""Low-level agy CLI subprocess execution for both JSON and stream-json output."""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator

from core.config import settings
from core.safe_runner import safe_run_command

logger = logging.getLogger(__name__)


class AgyProcessError(Exception):
    """Raised when agy subprocess fails."""

    def __init__(self, message: str, returncode: int, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def _build_command(
    prompt: str,
    agent: str,
    output_format: str = "json",
    json_schema: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    workspace: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Build the agy CLI command list.

    Args:
        prompt: The user prompt to send to agy.
        agent: The agent name to use (e.g., 'read').
        output_format: Output format ('json' or 'stream-json').
        json_schema: Optional JSON schema to enforce on output.
        conversation_id: Optional conversation ID for multi-turn.
        workspace: Optional workspace directory path.
        model: Optional model name (defaults to settings.agy_default_model).

    Returns:
        List of command arguments for subprocess execution.
    """
    selected_model = model or settings.agy_default_model
    cmd = [
        settings.agy_binary,
        "--print", prompt,
        "--agent", agent,
        "--output-format", output_format,
    ]

    if selected_model:
        cmd.extend(["--model", selected_model])

    workspace_path = workspace or settings.agy_default_workspace
    cmd.extend(["--add-dir", str(Path(workspace_path).expanduser().resolve())])

    if json_schema:
        cmd.extend(["--json-schema", json.dumps(json_schema)])
    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    return cmd


async def run_agy(
    prompt: str,
    agent: str,
    json_schema: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Execute agy with --output-format json (non-streaming).

    Args:
        prompt: The user prompt.
        agent: The agent name.
        json_schema: Optional JSON schema for structured output.
        conversation_id: Optional conversation ID for multi-turn.
        workspace: Optional workspace directory.
        timeout: Execution timeout in seconds.
        model: Optional model name.

    Returns:
        Parsed JSON response dict from agy.

    Raises:
        AgyProcessError: If agy exits with non-zero code or output is unparseable.
    """
    cmd = _build_command(
        prompt=prompt,
        agent=agent,
        output_format="json",
        json_schema=json_schema,
        conversation_id=conversation_id,
        workspace=workspace,
        model=model,
    )
    timeout = timeout or settings.agy_default_timeout

    logger.info(
        "Executing agy (non-streaming)",
        extra={"agent": agent, "conversation_id": conversation_id, "model": model},
    )
    start = time.monotonic()

    res = await safe_run_command(
        cmd,
        cwd=Path(workspace or settings.agy_default_workspace).expanduser().resolve(),
        timeout=timeout,
        override_stdin_devnull=True,
    )

    logger.info(
        "agy completed",
        extra={
            "agent": agent,
            "conversation_id": conversation_id,
            "duration_ms": res.duration_ms,
            "mitigated": res.was_mitigated,
        },
    )

    stdout_text = res.stdout
    stderr_text = res.stderr

    data = None
    if stdout_text.strip():
        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError:
            pass

    if res.returncode != 0 or (data and data.get("status") == "ERROR"):
        error_msg = f"agy exited with code {res.returncode}"
        if data and isinstance(data, dict) and data.get("error"):
            error_msg = str(data["error"])
        elif stderr_text.strip():
            error_msg = stderr_text.strip()

        logger.error(
            f"agy execution error: {error_msg}",
            extra={"stderr": stderr_text[:500]},
        )
        raise AgyProcessError(
            error_msg,
            res.returncode or 1,
            stderr_text,
        )

    if data is not None:
        return data

    raise AgyProcessError(
        "Empty or invalid stdout output from agy",
        res.returncode or 0,
        stderr_text,
    )


async def stream_agy(
    prompt: str,
    agent: str,
    json_schema: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Execute agy with --output-format stream-json (streaming).

    Yields parsed NDJSON event dicts line-by-line as agy produces them.

    Args:
        prompt: The user prompt.
        agent: The agent name.
        json_schema: Optional JSON schema for structured output.
        conversation_id: Optional conversation ID for multi-turn.
        workspace: Optional workspace directory.
        timeout: Execution timeout in seconds (unused for streaming).
        model: Optional model name.

    Yields:
        Parsed JSON event dicts from agy's NDJSON stream.

    Raises:
        AgyProcessError: If agy exits with non-zero code.
    """
    cmd = _build_command(
        prompt=prompt,
        agent=agent,
        output_format="stream-json",
        json_schema=json_schema,
        conversation_id=conversation_id,
        workspace=workspace,
        model=model,
    )

    logger.info(
        "Executing agy (streaming)",
        extra={"agent": agent, "conversation_id": conversation_id},
    )

    exec_env = dict(os.environ)
    exec_env["PAGER"] = "cat"
    exec_env["GIT_PAGER"] = "cat"
    exec_env["TERM"] = "dumb"

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        cwd=Path(workspace or settings.agy_default_workspace).expanduser().resolve(),
        env=exec_env,
    )

    assert proc.stdout is not None, "proc.stdout must be PIPE"
    assert proc.stderr is not None, "proc.stderr must be PIPE"

    try:
        async for line in proc.stdout:
            decoded = line.decode("utf-8").strip()
            if not decoded:
                continue
            try:
                event = json.loads(decoded)
                yield event
            except json.JSONDecodeError:
                logger.warning(f"Skipping non-JSON line from agy: {decoded[:100]}")
                continue
    finally:
        await proc.wait()
        if proc.returncode != 0:
            stderr = await proc.stderr.read()
            stderr_text = stderr.decode("utf-8", errors="replace")
            logger.error(
                f"agy stream exited with code {proc.returncode}",
                extra={"stderr": stderr_text[:500]},
            )
