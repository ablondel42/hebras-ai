from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.agy_interactive import InteractiveSession

logger = logging.getLogger(__name__)


@dataclass
class AgySession:
    """Represents a conversation session with an agy agent and underlying model.

    Each session tracks the agy conversation_id, agent persona, LLM model,
    workspace, and lifecycle metadata (creation time, last active time, turn count).
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    agent: str = "default"
    model: str = "Gemini 3.7 Flash"
    conversation_id: str | None = None  # agy's conversation UUID
    workspace: str | None = None
    mode: str = "headless"  # "headless" or "interactive"
    interactive: InteractiveSession | None = None  # InteractiveSession instance when mode="interactive"
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)
    turn_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    async def cleanup(self) -> None:
        """Clean up resources attached to this session (close PTY process)."""
        if self.interactive is not None:
            try:
                await self.interactive.close()
            except Exception as e:
                logger.warning(f"Error cleaning up interactive session {self.session_id}: {e}")
            self.interactive = None

    def touch(self) -> None:
        """Update last active timestamp and increment turn count."""
        self.last_active = time.monotonic()
        self.turn_count += 1

    def is_expired(self, idle_timeout: int) -> bool:
        """Check if session has been idle longer than the timeout.

        Args:
            idle_timeout: Maximum idle time in seconds.

        Returns:
            True if the session has expired.
        """
        return (time.monotonic() - self.last_active) > idle_timeout

    @property
    def agent_id(self) -> str:
        """Agent persona ID for this session."""
        return self.agent

    @property
    def model_id(self) -> str:
        """Underlying LLM model ID for this session."""
        return self.model
