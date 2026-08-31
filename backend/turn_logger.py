"""Turn logger for recording complete prompts, responses, and evaluation metadata."""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.config import settings

logger = logging.getLogger(__name__)


def is_test_environment() -> bool:
    """Check if the current process is executing within a test suite."""
    if os.environ.get("HEBRAS_DISABLE_FILE_LOGGING") == "1":
        return True
    if os.environ.get("PYTEST_CURRENT_TEST") is not None:
        return True
    if "pytest" in sys.modules:
        return True
    return False


def get_log_datetime() -> datetime:
    """Return the current datetime in the configured or local system timezone."""
    if settings.log_timezone:
        try:
            return datetime.now(ZoneInfo(settings.log_timezone))
        except Exception as e:
            logger.debug(f"Invalid or unsupported log timezone '{settings.log_timezone}': {e}")
    return datetime.now().astimezone()


def log_turn(
    conversation_id: str,
    turn: int,
    agent: str,
    model: str,
    target_model: str,
    reflection: str,
    mode: str,
    prompt: str,
    system_prompt: str | None,
    response_text: str,
    usage: dict[str, Any] | None = None,
    duration_s: float | None = None,
    workspace: str | None = None,
    force_write: bool = False,
) -> Path | None:
    """Log a complete turn (prompt + response + metadata) to the conversation log file.

    Args:
        conversation_id: Unique conversation UUID.
        turn: Current turn index (1-based).
        agent: Agent persona used.
        model: Clean model name.
        target_model: Target model argument passed to agy.
        reflection: Reflection/effort level (low, medium, high).
        mode: Execution mode ('non-streaming', 'streaming', 'interactive').
        prompt: The user prompt text.
        system_prompt: Optional system prompt text.
        response_text: The complete generated response text.
        usage: Optional token usage dict.
        duration_s: Optional duration in seconds.
        workspace: Optional workspace directory path.
        force_write: If True, writes even in test environments.

    Returns:
        Path to written log file, or None if skipped.
    """
    if not force_write and is_test_environment():
        return None

    try:
        ws_path = Path(workspace or ".").expanduser().resolve()
        log_dir = ws_path / settings.agy_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{conversation_id}.log"

        now = get_log_datetime()
        tz_name = now.strftime("%Z") or now.strftime("%z")
        timestamp = now.strftime(f"%Y-%m-%d %H:%M:%S {tz_name}").strip()

        tokens_line = ""
        if usage:
            in_tok = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            out_tok = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            think_tok = usage.get("thinking_tokens") or 0
            tot_tok = usage.get("total_tokens") or (in_tok + out_tok)
            tokens_line = f"Tokens: {in_tok} input, {out_tok} output, {think_tok} thinking ({tot_tok} total)\n"

        dur_line = f"Duration: {duration_s:.3f}s\n" if duration_s is not None else ""

        entry = (
            f"{'=' * 80}\n"
            f"[{timestamp}] Conversation ID: {conversation_id} | Turn: {turn}\n"
            f"Agent: {agent} | Model: {model} | Level: {reflection} (Target: {target_model})\n"
            f"Mode: {mode}\n"
            f"{dur_line}"
            f"{tokens_line}"
            f"{'-' * 80}\n"
            f"[SYSTEM INSTRUCTIONS]\n{system_prompt or '(None)'}\n\n"
            f"[USER PROMPT]\n{prompt}\n"
            f"{'-' * 80}\n"
            f"[RESPONSE]\n{response_text}\n"
            f"{'=' * 80}\n\n"
        )

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

        return log_file
    except Exception as e:
        logger.warning(f"Failed to write turn evaluation log for {conversation_id}: {e}")
        return None
