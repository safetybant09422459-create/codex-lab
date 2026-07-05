from __future__ import annotations

from typing import Any

from .chat_core import EntityResolutionRequest, EntityResolutionResult
from .travel_chat_adapter import TRAVEL_SKILL_ID, TRIP_ENTITY_TYPE


class TravelEntityResolver:
    """Resolve Travel Trip candidates without crossing the Runtime boundary."""

    resolver_id = "travel_entity_resolver"

    def __init__(self, *, search_index: Any = None) -> None:
        self._search_index = search_index

    def resolve(
        self,
        request: EntityResolutionRequest,
        *,
        trips: Any = None,
        runtime_result: Any = None,
    ) -> EntityResolutionResult:
        if request.skill_id not in (None, TRAVEL_SKILL_ID):
            return self._not_found("skill_id_mismatch")
        if (
            request.entity_types is not None
            and TRIP_ENTITY_TYPE not in request.entity_types
        ):
            return self._not_found("entity_type_mismatch")

        return EntityResolutionResult(
            status="needs_context",
            reason="python_semantic_resolution_disabled",
            diagnostics={
                "resolver": self.resolver_id,
                "candidate_count": 0,
                "top_candidate_score": None,
            },
        )

    def _not_found(self, reason: str) -> EntityResolutionResult:
        return EntityResolutionResult(
            status="not_found",
            reason=reason,
            diagnostics={
                "resolver": self.resolver_id,
                "candidate_count": 0,
                "top_candidate_score": None,
            },
        )
