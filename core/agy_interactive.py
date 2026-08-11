"""Interactive agy PTY session management with Transcript Log Synchronization.

Spawns agy in a background PTY process, maintaining persistent TUI/agent state.
Message completion and response extraction are synchronized directly via agy's
internal structured transcript log (transcript_full.jsonl), ensuring 100%
deterministic response detection with zero ANSI or screen-scraping flakiness.
"""
import asyncio
import glob
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import pexpect

from core.config import settings

logger = logging.getLogger(__name__)

RESPONSE_TIMEOUT = 180  # seconds


class InteractiveSessionError(Exception):
    """Raised when interactive session execution fails."""
    pass


class InteractiveSession:
    """Persistent, invisible pexpect-managed agy session backed by transcript logs."""

    def __init__(
        self,
        agent: str,
        workspace: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        auto_approve: bool | None = None,
        conversation_id: str | None = None,
    ):
        self.agent = agent
        self.workspace = workspace or settings.agy_default_workspace
        self.model = model or settings.agy_default_model
        self.mode = mode or settings.agy_default_mode
        self.auto_approve = settings.agy_dangerously_skip_permissions if auto_approve is None else auto_approve
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.child: pexpect.spawn | None = None
        self._dump_file: Any = None
        self._lock = asyncio.Lock()
        self._started = False
        self._transcript_line_count = 0

    @property
    def log_file_path(self) -> Path:
        """Path to explicit agy CLI session log file."""
        ws_path = Path(self.workspace).expanduser().resolve()
        log_dir = ws_path / settings.agy_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{self.conversation_id}.log"

    @property
    def pty_dump_file_path(self) -> Path:
        """Path to full raw PTY output dump log file."""
        ws_path = Path(self.workspace).expanduser().resolve()
        log_dir = ws_path / settings.agy_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"pty_dump_{self.conversation_id}.log"

    @property
    def transcript_path(self) -> Path:
        """Path to agy's internal transcript_full.jsonl log file."""
        return (
            Path.home()
            / ".gemini"
            / "antigravity-cli"
            / "brain"
            / self.conversation_id
            / ".system_generated"
            / "logs"
            / "transcript_full.jsonl"
        )

    def _drain_pty_buffer(self) -> None:
        """Non-blocking drain of OS PTY buffer to prevent process kernel block and flush logfile."""
        if self.child is not None and self.child.isalive():
            try:
                self.child.read_nonblocking(65536, timeout=0.01)
            except (pexpect.TIMEOUT, pexpect.EOF, Exception):
                pass

    async def start(self) -> None:
        """Spawn the agy process with PTY output dump logging enabled."""
        cmd_parts = [
            settings.agy_binary,
            "--agent", self.agent,
            "--log-file", str(self.log_file_path),
            "--add-dir", str(Path(self.workspace).expanduser().resolve()),
        ]

        if self.mode:
            cmd_parts.extend(["--mode", self.mode])

        # Only pass --conversation if the conversation ID already exists on disk
        if self.transcript_path.exists():
            cmd_parts.extend(["--conversation", self.conversation_id])

        if self.model:
            cmd_parts.extend(["--model", self.model])
        if self.auto_approve:
            cmd_parts.append("--dangerously-skip-permissions")

        cmd = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)

        env = dict(os.environ)
        env["TERM"] = "dumb"
        env["PAGER"] = "cat"
        env["NO_COLOR"] = "1"

        logger.info(
            f"Starting transcript-backed agy session: agent={self.agent} conversation_id={self.conversation_id} mode={self.mode} pty_dump={self.pty_dump_file_path}"
        )

        try:
            self._dump_file = open(self.pty_dump_file_path, "w", encoding="utf-8", buffering=1)
            self.child = pexpect.spawn(
                cmd,
                timeout=RESPONSE_TIMEOUT,
                encoding="utf-8",
                maxread=65536,
                env=env,
            )
            self.child.logfile = self._dump_file
            self._started = True
        except Exception as e:
            raise InteractiveSessionError(f"Failed to spawn agy interactive process: {e}") from e

        # Wait 4 seconds for agy startup & drain initial PTY buffer
        start_t = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_t) < 4.0:
            self._drain_pty_buffer()
            await asyncio.sleep(0.2)

        self._transcript_line_count = self._get_transcript_line_count()
        logger.info(f"agy session {self.conversation_id} ready for input")

    async def send_message(self, message: str) -> str:
        """Send prompt to PTY using \\r (Carriage Return) and await response from transcript log.

        Args:
            message: User prompt text.

        Returns:
            Clean assistant response text extracted directly from transcript_full.jsonl.

        Raises:
            InteractiveSessionError: If session dies or times out.
        """
        async with self._lock:
            if not self.is_alive():
                raise InteractiveSessionError("Interactive session is not alive")

            logger.info(
                f"Sending prompt to agy session ({self.agent}): '{message[:80]}...'"
            )

            assert self.child is not None
            brain_root = Path.home() / ".gemini" / "antigravity-cli" / "brain"
            dirs_before = set(glob.glob(str(brain_root / "*")))

            self._transcript_line_count = self._get_transcript_line_count()
            
            # Send prompt with \r (Carriage Return) to trigger Bubbletea form submit
            self.child.send(f"{message}\r")

            # Await brain directory resolution if this turn creates a new session folder
            start_t = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_t) < 15.0:
                self._drain_pty_buffer()
                if self.transcript_path.exists():
                    break
                dirs_after = set(glob.glob(str(brain_root / "*"))) - dirs_before
                if dirs_after:
                    assigned_id = Path(list(dirs_after)[0]).name
                    logger.info(f"Discovered active agy session conversation_id: {assigned_id}")
                    self.conversation_id = assigned_id
                    break
                await asyncio.sleep(0.3)

            return await self._await_response_from_transcript()

    async def _await_response_from_transcript(self) -> str:
        """Poll transcript_full.jsonl for new MODEL PLANNER_RESPONSE with content."""
        start_time = asyncio.get_event_loop().time()
        start_line = self._transcript_line_count

        while (asyncio.get_event_loop().time() - start_time) < RESPONSE_TIMEOUT:
            if not self.is_alive():
                raise InteractiveSessionError("agy PTY process terminated unexpectedly")

            self._drain_pty_buffer()

            if self.transcript_path.exists():
                try:
                    lines = self.transcript_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if len(lines) > start_line:
                        for line in lines[start_line:]:
                            if not line.strip():
                                continue
                            try:
                                entry = json.loads(line)
                                if (
                                    entry.get("source") == "MODEL"
                                    and entry.get("type") == "PLANNER_RESPONSE"
                                    and entry.get("content")
                                ):
                                    response_text = str(entry["content"]).strip()
                                    self._transcript_line_count = len(lines)
                                    logger.info(
                                        f"Extracted response from transcript log: length={len(response_text)}"
                                    )
                                    return response_text
                            except json.JSONDecodeError:
                                pass
                except Exception as e:
                    logger.debug(f"Reading transcript log: {e}")

            await asyncio.sleep(0.3)

        raise InteractiveSessionError(
            f"Timed out after {RESPONSE_TIMEOUT}s waiting for transcript response"
        )

    def _get_transcript_line_count(self) -> int:
        """Count current lines in transcript log file."""
        if self.transcript_path.exists():
            try:
                return len(self.transcript_path.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                return 0
        return 0

    def is_alive(self) -> bool:
        """Check if PTY process is currently running."""
        return self.child is not None and self._started and self.child.isalive()

    async def close(self) -> None:
        """Close the PTY process cleanly."""
        if self.child is not None:
            logger.info(f"Closing agy session {self.conversation_id}")
            try:
                if self.child.isalive():
                    self.child.send("exit\r")
                    await asyncio.sleep(0.3)
                self.child.close(force=True)
            except Exception as e:
                logger.warning(f"Error closing agy session: {e}")
            finally:
                self.child = None
                self._started = False
                if self._dump_file:
                    try:
                        self._dump_file.close()
                    except Exception:
                        pass
                    self._dump_file = None
