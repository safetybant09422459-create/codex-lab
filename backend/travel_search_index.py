from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .core_models import EntityCandidate
from .search_engine import SearchEngine
from .travel_document_builder import TravelDocumentBuilder
from .travel_search_expansion import (
    TravelSearchExpansionProvider,
    expand_travel_query,
    normalize_travel_query,
)

__all__ = (
    "TravelSearchIndex",
    "expand_travel_query",
    "normalize_travel_query",
)


class TravelSearchIndex:
    """Compatibility facade composing Travel adapters with the common engine."""

    def __init__(
        self,
        *,
        builder: TravelDocumentBuilder | None = None,
        expansion: TravelSearchExpansionProvider | None = None,
        engine: SearchEngine | None = None,
    ) -> None:
        self._builder = builder or TravelDocumentBuilder()
        self._expansion = expansion or TravelSearchExpansionProvider()
        self._engine = engine or SearchEngine()

    def search(
        self,
        query: str,
        trips: Iterable[dict[str, Any]],
    ) -> list[EntityCandidate]:
        terms = self._expansion.terms(query)
        if not terms:
            return []
        documents = self._builder.build_many(
            trips,
            verified_at=datetime.now(timezone.utc),
        )
        return self._engine.search(terms, documents)
