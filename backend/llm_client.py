from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .agent_host import LLMInputPayload


@runtime_checkable
class LLMClient(Protocol):
    """Provider-neutral interface used by the Jarvis single agent loop."""

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]: ...


class AIModelProviderAdapter:
    """Stub boundary for a future AI model provider implementation."""

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]:
        raise NotImplementedError("AI model provider connection is not implemented")
