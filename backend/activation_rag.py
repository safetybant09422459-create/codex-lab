from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .rag_core import RagDocument, RagEntityType, RagSearchResult
from .rag_store import InMemoryRagStore
from .travel_rag_provider import TravelRagProvider


# PoC tuning values. Keep these explicit so validation can adjust them without
# changing the store's scoring contract.
ACTIVATION_MIN_SCORE = 0.25
ACTIVATION_OVERSAMPLE_FACTOR = 10
MAX_EXPERIENCES_PER_TRIP = 2


class RagDocumentProvider(Protocol):
    def documents(self) -> list[RagDocument]: ...


class RagStore(Protocol):
    def replace(self, documents: Iterable[RagDocument]) -> None: ...

    def search(
        self,
        query: str,
        *,
        limit: int,
        source_skill: str | None,
        entity_type: RagEntityType | None,
        allowed_visibilities: set[str] | None,
    ) -> list[RagSearchResult]: ...


class ActivationRag:
    def __init__(
        self,
        providers: Iterable[RagDocumentProvider],
        store: RagStore | None = None,
    ) -> None:
        self.providers = tuple(providers)
        self.store: RagStore = store or InMemoryRagStore()

    def refresh(self) -> int:
        documents = [
            document
            for provider in self.providers
            for document in provider.documents()
        ]
        self.store.replace(documents)
        return len(documents)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        source_skill: str | None = None,
        entity_type: RagEntityType | None = None,
        allowed_visibilities: set[str] | None = None,
    ) -> list[RagSearchResult]:
        self.refresh()
        candidates = self.store.search(
            query,
            limit=max(limit, limit * ACTIVATION_OVERSAMPLE_FACTOR),
            source_skill=source_skill,
            entity_type=entity_type,
            allowed_visibilities=allowed_visibilities,
        )
        return _select_candidates(candidates, limit=limit)


def _select_candidates(
    candidates: Iterable[RagSearchResult], *, limit: int
) -> list[RagSearchResult]:
    """Apply conservative PoC filtering while preserving ranked order."""
    if limit <= 0:
        return []

    selected: list[RagSearchResult] = []
    experiences_by_trip: dict[str, int] = {}
    for candidate in candidates:
        if candidate.score < ACTIVATION_MIN_SCORE:
            continue
        trip_id = candidate.document.metadata.get("trip_id")
        if candidate.document.entity_type == "experience" and isinstance(
            trip_id, str
        ):
            count = experiences_by_trip.get(trip_id, 0)
            if count >= MAX_EXPERIENCES_PER_TRIP:
                continue
            experiences_by_trip[trip_id] = count + 1
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def activation_search(
    query: str,
    limit: int = 5,
    *,
    source_skill: str | None = None,
    entity_type: RagEntityType | None = None,
    allowed_visibilities: set[str] | None = None,
    providers: Iterable[RagDocumentProvider] | None = None,
) -> list[RagSearchResult]:
    """Recall candidates only; callers must resolve entities through Runtime."""
    rag = ActivationRag(providers or (TravelRagProvider(),))
    return rag.search(
        query,
        limit=limit,
        source_skill=source_skill,
        entity_type=entity_type,
        allowed_visibilities=allowed_visibilities,
    )
