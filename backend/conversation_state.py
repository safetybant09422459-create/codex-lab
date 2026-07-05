from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class ConversationTurnState:
    user_input: dict[str, Any]
    assistant_final_response: str
    last_llm_action: dict[str, Any]
    last_observations: list[dict[str, Any]] = field(default_factory=list)
    active_entities: list[dict[str, Any]] = field(default_factory=list)


class InMemoryConversationStateStore:
    """Bounded, process-local conversation state keyed only by session ID.

    This store preserves LLM inputs and outputs without interpreting them.
    It is intentionally not a repository or persistent Memory provider.
    """

    def __init__(self, max_turns: int = 5) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.max_turns = max_turns
        self._sessions: dict[str, list[ConversationTurnState]] = {}
        self._session_started_at: dict[str, str] = {}
        self._lock = RLock()

    def get_turns(self, session_id: str) -> list[ConversationTurnState]:
        with self._lock:
            return deepcopy(self._sessions.get(session_id, []))

    def append_turn(self, session_id: str, turn: ConversationTurnState) -> None:
        with self._lock:
            self.get_or_create_started_at(session_id)
            turns = self._sessions.setdefault(session_id, [])
            turns.append(deepcopy(turn))
            del turns[:-self.max_turns]

    def get_or_create_started_at(self, session_id: str) -> str:
        with self._lock:
            return self._session_started_at.setdefault(
                session_id, datetime.now(timezone.utc).isoformat()
            )
