"""Session manager for maintaining conversation and process state."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import settings


@dataclass
class Session:
    """Represents an agent session."""

    session_id: str
    openbb_conversation_id: Optional[str] = None
    is_continued: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    # Session directory for persisted files
    _session_dir: Optional[Path] = field(default=None, repr=False)

    @property
    def session_dir(self) -> Path:
        """Get session directory path."""
        if self._session_dir is None:
            base_dir = settings.resolved_session_dir
            self._session_dir = base_dir / self.session_id
        return self._session_dir

    def ensure_session_dir(self) -> Path:
        """Create session directory if it doesn't exist."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active = datetime.utcnow()


class SessionManager:
    """Manages agent sessions for conversation context and process control.

    Features:
    - Session creation and lookup by OpenBB conversation ID
    - Session directory management for persisted context
    - Single-process execution lock (MVP constraint)
    - Process termination support
    """

    def __init__(self):
        # Maps OpenBB conversation ID to session
        self._sessions: dict[str, Session] = {}
        # Maps session ID to session (for direct lookup)
        self._sessions_by_id: dict[str, Session] = {}
        # Lock for concurrent access (single process queue)
        self._lock = asyncio.Lock()
        # Currently running process (for single-process model)
        self._current_process: Optional[asyncio.subprocess.Process] = None
        # Current session being processed
        self._current_session_id: Optional[str] = None

    def get_or_create_session(
        self, openbb_conversation_id: Optional[str] = None
    ) -> Session:
        """Get existing session or create a new one.

        Args:
            openbb_conversation_id: Optional conversation ID from OpenBB Copilot.
                If provided and a session exists, returns the existing session.
                If not provided, creates a new session without tracking.

        Returns:
            Session object with session_id and continuation flag.
        """
        if openbb_conversation_id and openbb_conversation_id in self._sessions:
            session = self._sessions[openbb_conversation_id]
            session.is_continued = True
            session.touch()
            return session

        # Create new session
        session = Session(
            session_id=str(uuid.uuid4()),
            openbb_conversation_id=openbb_conversation_id,
        )

        if openbb_conversation_id:
            self._sessions[openbb_conversation_id] = session

        self._sessions_by_id[session.session_id] = session
        return session

    def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by its session ID.

        Args:
            session_id: The session ID.

        Returns:
            Session if found, None otherwise.
        """
        return self._sessions_by_id.get(session_id)

    def clear_session(self, openbb_conversation_id: str) -> bool:
        """Clear a specific session.

        Args:
            openbb_conversation_id: The OpenBB conversation ID to clear.

        Returns:
            True if session was found and cleared, False otherwise.
        """
        if openbb_conversation_id in self._sessions:
            session = self._sessions[openbb_conversation_id]
            # Remove from both mappings
            del self._sessions[openbb_conversation_id]
            if session.session_id in self._sessions_by_id:
                del self._sessions_by_id[session.session_id]
            return True
        return False

    def clear_all_sessions(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared.
        """
        count = len(self._sessions)
        self._sessions.clear()
        self._sessions_by_id.clear()
        return count

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions.

        Returns:
            List of session info dicts.
        """
        return [
            {
                "session_id": s.session_id,
                "openbb_conversation_id": s.openbb_conversation_id,
                "created_at": s.created_at.isoformat(),
                "last_active": s.last_active.isoformat(),
                "is_continued": s.is_continued,
            }
            for s in self._sessions_by_id.values()
        ]

    async def acquire_process_lock(self) -> bool:
        """Acquire the process lock for single-process execution.

        Returns:
            True if lock was acquired.
        """
        await self._lock.acquire()
        return True

    def release_process_lock(self) -> None:
        """Release the process lock."""
        if self._lock.locked():
            self._lock.release()

    def set_current_process(
        self,
        process: Optional[asyncio.subprocess.Process],
        session_id: Optional[str] = None,
    ) -> None:
        """Set the currently running Claude Code process.

        Args:
            process: The subprocess, or None to clear.
            session_id: The session ID associated with this process.
        """
        self._current_process = process
        self._current_session_id = session_id

    def get_current_process(self) -> Optional[asyncio.subprocess.Process]:
        """Get the currently running Claude Code process.

        Returns:
            The current subprocess, or None if not running.
        """
        return self._current_process

    async def terminate_current_process(self) -> bool:
        """Terminate the currently running process if any.

        Returns:
            True if a process was terminated, False if no process was running.
        """
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()
            try:
                await asyncio.wait_for(self._current_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._current_process.kill()
                await self._current_process.wait()
            self._current_process = None
            self._current_session_id = None
            return True
        return False

    def persist_context(self, session: Session, context: dict[str, Any]) -> Path:
        """Persist request context to session directory.

        Args:
            session: The session to persist context for.
            context: The context data to persist.

        Returns:
            Path to the persisted context file.
        """
        session_dir = session.ensure_session_dir()
        context_file = session_dir / "request_context.json"

        with open(context_file, "w") as f:
            json.dump(context, f, indent=2, default=str)

        return context_file

    def load_context(self, session: Session) -> Optional[dict[str, Any]]:
        """Load persisted context from session directory.

        Args:
            session: The session to load context for.

        Returns:
            Context data if found, None otherwise.
        """
        context_file = session.session_dir / "request_context.json"
        if context_file.exists():
            with open(context_file) as f:
                return json.load(f)
        return None


# Global session manager instance
session_manager = SessionManager()
