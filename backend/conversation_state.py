from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable


@dataclass
class ConversationTurnState:
    user_input: dict[str, Any]
    assistant_final_response: str
    last_llm_action: dict[str, Any]
    last_observations: list[dict[str, Any]] = field(default_factory=list)
    active_entities: list[dict[str, Any]] = field(default_factory=list)
    source: str = "server_turn"


class InMemoryConversationStateStore:
    """Bounded, process-local conversation state keyed only by session ID.

    This store preserves LLM inputs and outputs without interpreting them.
    It is intentionally not a repository or persistent Memory provider.
    """

    def __init__(
        self,
        max_turns: int = 5,
        max_sessions: int = 256,
        session_ttl: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        if max_sessions < 1:
            raise ValueError("max_sessions must be at least 1")
        if session_ttl <= timedelta(0):
            raise ValueError("session_ttl must be positive")
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self.session_ttl = session_ttl
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, list[ConversationTurnState]] = {}
        self._session_started_at: dict[str, str] = {}
        self._session_last_accessed_at: dict[str, datetime] = {}
        self._lock = RLock()

    def get_turns(self, session_id: str) -> list[ConversationTurnState]:
        with self._lock:
            now = self._now()
            self._prune_expired(now)
            if session_id in self._session_started_at:
                self._session_last_accessed_at[session_id] = now
            return deepcopy(self._sessions.get(session_id, []))

    def append_turn(self, session_id: str, turn: ConversationTurnState) -> None:
        with self._lock:
            now = self._now()
            self._prune_expired(now)
            self._ensure_session(session_id, now)
            turns = self._sessions.setdefault(session_id, [])
            turns.append(deepcopy(turn))
            del turns[:-self.max_turns]

    def get_or_create_started_at(self, session_id: str) -> str:
        with self._lock:
            now = self._now()
            self._prune_expired(now)
            self._ensure_session(session_id, now)
            return self._session_started_at[session_id]

    def clear_session(self, session_id: str) -> None:
        """Delete working context without treating it as long-term Memory."""
        with self._lock:
            self._remove_session(session_id)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError(
                "conversation state clock must return a timezone-aware datetime"
            )
        return now.astimezone(timezone.utc)

    def _ensure_session(self, session_id: str, now: datetime) -> None:
        if session_id not in self._session_started_at:
            self._evict_for_capacity()
            self._session_started_at[session_id] = now.isoformat()
        self._session_last_accessed_at[session_id] = now

    def _prune_expired(self, now: datetime) -> None:
        expired = [
            session_id
            for session_id, accessed_at in self._session_last_accessed_at.items()
            if now - accessed_at >= self.session_ttl
        ]
        for session_id in expired:
            self._remove_session(session_id)

    def _evict_for_capacity(self) -> None:
        while len(self._session_started_at) >= self.max_sessions:
            oldest = min(
                self._session_started_at,
                key=lambda session_id: self._session_last_accessed_at[session_id],
            )
            self._remove_session(oldest)

    def _remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._session_started_at.pop(session_id, None)
        self._session_last_accessed_at.pop(session_id, None)
