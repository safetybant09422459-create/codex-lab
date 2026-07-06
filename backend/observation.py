from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class ObservationEnvelope(BaseModel):
    """Provider result plus deterministic facts for the LLM agent loop."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    operation_id: str
    status: str
    raw_result: dict[str, Any]
    facts: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any]
    visibility: str = "unknown"
    freshness: str = "observed_at_execution"
    observed_at: str
    related_capabilities: list[str] = Field(default_factory=list)


class ObservationEnvelopeBuilder:
    """Builds an envelope without interpreting user text or choosing actions."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def build(
        self,
        *,
        provider_id: str,
        operation_id: str,
        raw_result: dict[str, Any],
        details: dict[str, Any] | None = None,
    ) -> ObservationEnvelope:
        details = details or {}
        return ObservationEnvelope(
            provider_id=provider_id,
            operation_id=operation_id,
            status=self._status(raw_result),
            raw_result=deepcopy(raw_result),
            facts=deepcopy(details.get("facts", {})),
            counts=deepcopy(details.get("counts", {})),
            limitations=list(details.get("limitations", ())),
            provenance={
                "provider_id": provider_id,
                "operation_id": operation_id,
                "execution_mode": raw_result.get("execution_mode"),
                "source": self._source(raw_result),
                "source_refs": [],
            },
            visibility=str(details.get("visibility", "unknown")),
            observed_at=self._clock().astimezone(timezone.utc).isoformat(),
            related_capabilities=list(details.get("related_capabilities", ())),
        )

    @staticmethod
    def _status(raw_result: dict[str, Any]) -> str:
        if raw_result.get("permission_denied"):
            return "permission_denied"
        if raw_result.get("blocked"):
            return "blocked"
        return "success" if raw_result.get("success") is True else "failed"

    @staticmethod
    def _source(raw_result: dict[str, Any]) -> Any:
        result = raw_result.get("result")
        return result.get("source") if isinstance(result, dict) else None
