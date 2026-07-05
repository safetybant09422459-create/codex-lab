from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperationContext:
    """Runtime-validated operation metadata passed to a Domain Provider."""

    operation_id: str
    skill_id: str
    mode: str
    risk_level: str


@dataclass(frozen=True)
class ProviderOperationSpec:
    """Provider-owned semantics layered on Runtime-owned Tool metadata."""

    operation_id: str
    what_it_can_do: str
    what_it_cannot_do: str
    examples: tuple[dict[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()
    availability: str = "implemented"
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    mode: str | None = None
    risk_level: str | None = None
    confirmation_required: bool | None = None


class DomainProvider(ABC):
    """Deterministic capability boundary used after Runtime policy checks.

    Providers execute an already-selected operation. They do not interpret a
    user's utterance, choose a provider/operation, ask clarifying questions, or
    compose conversational answers.
    """

    provider_id: str

    @abstractmethod
    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        """Return deterministic capability metadata; never infer it from user text."""
        raise NotImplementedError

    @abstractmethod
    def execute(
        self, operation: OperationContext, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_execution_mode(self, operation: OperationContext) -> str:
        raise NotImplementedError
