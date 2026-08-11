"""SessionManager: manages a pool of AgySession instances with auto-expiry."""
import asyncio
import logging
from typing import Any

from core.config import settings
from core.session import AgySession

logger = logging.getLogger(__name__)


class SessionPoolFull(Exception):
    """Raised when the session pool has reached max capacity."""
    pass


class SessionNotFound(Exception):
    """Raised when a requested session doesn't exist or has expired."""
    pass


class SessionManager:
    """Manages a pool of AgySession instances with auto-expiry.

    The session manager maintains an in-memory dictionary of active sessions,
    enforces a configurable maximum pool size, and periodically evicts
    sessions that have been idle longer than the configured timeout.
    """

    def __init__(
        self,
        max_sessions: int | None = None,
        idle_timeout: int | None = None,
    ):
        self._sessions: dict[str, AgySession] = {}
        self._max_sessions = max_sessions or settings.max_sessions
        self._idle_timeout = idle_timeout or settings.session_idle_timeout
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"SessionManager started (max={self._max_sessions}, "
            f"idle_timeout={self._idle_timeout}s)"
        )

    async def stop(self) -> None:
        """Stop the cleanup task and clear all sessions."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        for session in self._sessions.values():
            await session.cleanup()
        self._sessions.clear()
        logger.info("SessionManager stopped")

    async def create_session(
        self,
        agent: str,
        workspace: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgySession:
        """Create a new session.

        Args:
            agent: The agy agent name to use.
            workspace: Optional workspace directory path.
            metadata: Optional metadata dict to attach to the session.

        Returns:
            The newly created AgySession.

        Raises:
            SessionPoolFull: If the pool has reached max capacity.
        """
        async with self._lock:
            self._evict_expired()
            if len(self._sessions) >= self._max_sessions:
                raise SessionPoolFull(
                    f"Session pool full ({self._max_sessions} max). "
                    "Close an existing session first."
                )
            session = AgySession(
                agent=agent,
                workspace=workspace,
                metadata=metadata or {},
            )
            self._sessions[session.session_id] = session
            logger.info(
                f"Created session {session.session_id}",
                extra={"session_id": session.session_id, "agent": agent},
            )
            return session

    async def get_session(self, session_id: str) -> AgySession:
        """Retrieve a session by session_id or conversation_id.

        Args:
            session_id: The session ID or conversation ID to look up.

        Returns:
            The matching AgySession.

        Raises:
            SessionNotFound: If the session doesn't exist or has expired.
        """
        session = self._sessions.get(session_id)
        if not session:
            for s in self._sessions.values():
                if s.conversation_id == session_id:
                    session = s
                    break

        if not session:
            raise SessionNotFound(f"Session {session_id} not found")
        if session.is_expired(self._idle_timeout):
            if session.session_id in self._sessions:
                del self._sessions[session.session_id]
            raise SessionNotFound(f"Session {session_id} expired")
        return session

    async def delete_session(self, session_id: str) -> None:
        """Explicitly delete a session.

        Args:
            session_id: The session ID to delete.
        """
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                await session.cleanup()
                logger.info(f"Deleted session {session_id}")

    async def list_sessions(self) -> list[AgySession]:
        """List all active (non-expired) sessions."""
        self._evict_expired()
        return list(self._sessions.values())

    def _evict_expired(self) -> None:
        """Remove expired sessions from the pool."""
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(self._idle_timeout)
        ]
        for sid in expired:
            session = self._sessions.pop(sid)
            if session.interactive is not None:
                asyncio.create_task(session.cleanup())
            logger.info(f"Evicted expired session {sid}")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired sessions."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            async with self._lock:
                self._evict_expired()
