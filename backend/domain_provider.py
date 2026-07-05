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


class DomainProvider(ABC):
    """Deterministic capability boundary used after Runtime policy checks.

    Providers execute an already-selected operation. They do not interpret a
    user's utterance, choose a provider/operation, ask clarifying questions, or
    compose conversational answers.
    """

    provider_id: str

    @abstractmethod
    def execute(
        self, operation: OperationContext, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_execution_mode(self, operation: OperationContext) -> str:
        raise NotImplementedError
