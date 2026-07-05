from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.agent_host import LLMInputPayload


class FakeLLMClient:
    """Deterministic LLMClient implementation for contract tests only."""

    def __init__(self, actions: dict[str, Any] | list[dict[str, Any]]) -> None:
        if isinstance(actions, list):
            if not actions:
                raise ValueError("Fake LLM requires at least one action")
            self.actions = deepcopy(actions)
        else:
            self.actions = [deepcopy(actions)]
        self.payloads: list[LLMInputPayload] = []

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]:
        self.payloads.append(payload.model_copy(deep=True))
        index = min(len(self.payloads) - 1, len(self.actions) - 1)
        return deepcopy(self.actions[index])
