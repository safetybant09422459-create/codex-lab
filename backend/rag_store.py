from __future__ import annotations

import re
from collections.abc import Iterable

from .rag_core import RagDocument, RagEntityType, RagSearchResult
from .search_engine import normalize_search_text


_QUERY_SEPARATORS = re.compile(
    r"(?:について|だった|行った|やった|いつ|何|どこ|教えて|見せて|"
    r"[\s、。,.!?！？をにはがでともへのや])"
)


class InMemoryRagStore:
    """Small replaceable v0.1 index with deterministic lexical ranking."""

    def __init__(self, documents: Iterable[RagDocument] = ()) -> None:
        self._documents: dict[str, RagDocument] = {}
        self.upsert(documents)

    def upsert(self, documents: Iterable[RagDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document

    def replace(self, documents: Iterable[RagDocument]) -> None:
        self._documents.clear()
        self.upsert(documents)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        source_skill: str | None = None,
        entity_type: RagEntityType | None = None,
        allowed_visibilities: set[str] | None = None,
    ) -> list[RagSearchResult]:
        if limit <= 0:
            return []
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            return []

        query_ngrams = _ngrams(normalized_query)
        query_terms = _query_terms(query)
        results: list[RagSearchResult] = []
        for document in self._documents.values():
            if source_skill is not None and document.source_skill != source_skill:
                continue
            if entity_type is not None and document.entity_type != entity_type:
                continue
            if (
                allowed_visibilities is not None
                and document.visibility not in allowed_visibilities
            ):
                continue
            result = _score(document, query_terms, query_ngrams)
            if result is not None:
                results.append(result)

        results.sort(
            key=lambda result: (
                -result.score,
                result.document.source_skill,
                result.document.entity_type,
                result.document.id,
            )
        )
        return results[:limit]


def _score(
    document: RagDocument,
    query_terms: tuple[str, ...],
    query_ngrams: set[str],
) -> RagSearchResult | None:
    text = normalize_search_text(document.text)
    if not text:
        return None
    matched_terms = [term for term in query_terms if term in text]
    overlap = query_ngrams & _ngrams(text)
    if not matched_terms and not overlap:
        return None

    term_strength = min(1.0, sum(len(term) for term in matched_terms) / 8.0)
    ngram_coverage = len(overlap) / max(1, len(query_ngrams))
    exact_phrase = any(len(term) >= 4 and term in text for term in matched_terms)
    score = min(
        1.0,
        0.12
        + 0.48 * term_strength
        + 0.34 * ngram_coverage
        + (0.06 if exact_phrase else 0.0),
    )
    display_terms = matched_terms or sorted(overlap, key=lambda value: (-len(value), value))[:5]
    reason = "lexical terms and character n-grams" if matched_terms else "character n-gram overlap"
    return RagSearchResult(
        document=document,
        score=round(score, 4),
        matched_terms=display_terms,
        reason=reason,
    )


def _query_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    normalized = normalize_search_text(query)
    for raw in _QUERY_SEPARATORS.split(query.casefold()):
        term = normalize_search_text(raw)
        if len(term) >= 2 and term not in terms:
            terms.append(term)
    # Preserve a complete short phrase such as "ドイツの森".
    if 2 <= len(normalized) <= 12 and normalized not in terms:
        terms.append(normalized)
    return tuple(terms)


def _ngrams(value: str, size: int = 2) -> set[str]:
    if len(value) < size:
        return {value} if value else set()
    return {value[index : index + size] for index in range(len(value) - size + 1)}
