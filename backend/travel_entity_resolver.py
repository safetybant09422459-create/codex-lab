from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .chat_core import EntityResolutionRequest, EntityResolutionResult
from .travel_chat_adapter import TRAVEL_SKILL_ID, TRIP_ENTITY_TYPE
from .travel_search_index import TravelSearchIndex


class TravelEntityResolver:
    """Resolve Travel Trip candidates without crossing the Runtime boundary."""

    resolver_id = "travel_entity_resolver"

    def __init__(self, *, search_index: TravelSearchIndex | None = None) -> None:
        self._search_index = search_index or TravelSearchIndex()

    def resolve(
        self,
        request: EntityResolutionRequest,
        *,
        trips: Iterable[dict[str, Any]] | None = None,
        runtime_result: Any = None,
    ) -> EntityResolutionResult:
        if request.skill_id not in (None, TRAVEL_SKILL_ID):
            return self._not_found("skill_id_mismatch")
        if (
            request.entity_types is not None
            and TRIP_ENTITY_TYPE not in request.entity_types
        ):
            return self._not_found("entity_type_mismatch")

        source_trips = list(trips) if trips is not None else _runtime_trips(runtime_result)
        candidates = self._search_index.search(request.query, source_trips)[
            : request.limit
        ]
        diagnostics = {
            "resolver": self.resolver_id,
            "candidate_count": len(candidates),
            "top_candidate_score": candidates[0].score if candidates else None,
        }
        if not candidates:
            return EntityResolutionResult(
                status="not_found",
                reason="no_candidates",
                diagnostics=diagnostics,
            )
        if len(candidates) == 1:
            return EntityResolutionResult(
                status="resolved",
                candidates=candidates,
                resolved_entity=candidates[0].entity,
                reason="single_candidate",
                diagnostics=diagnostics,
            )
        return EntityResolutionResult(
            status="ambiguous",
            candidates=candidates,
            reason="multiple_candidates",
            diagnostics=diagnostics,
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


def _runtime_trips(runtime_result: Any) -> list[dict[str, Any]]:
    if not isinstance(runtime_result, dict):
        return []
    trips = runtime_result.get("trips")
    if not isinstance(trips, list):
        return []
    return [trip for trip in trips if isinstance(trip, dict)]
