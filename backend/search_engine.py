from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .chat_core import EntityCandidate, EntityRef


class SearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchKeyword(SearchModel):
    """A searchable field and its ranking policy.

    Field names and weights are supplied by a document builder. The engine does
    not need to know which Skill or entity produced the field.
    """

    value: str
    matched_by: str
    exact_matched_by: str | None = None
    partial_matched_by: str | None = None
    exact_score: float = Field(ge=0.0, le=1.0)
    partial_score: float = Field(ge=0.0, le=1.0)


class SearchDocument(SearchModel):
    """Skill-neutral input consumed by SearchEngine."""

    id: str
    label: str
    document: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    keywords: tuple[SearchKeyword, ...] = ()


class SearchTerm(SearchModel):
    """A normalized query term with caller-defined provenance and strength."""

    value: str
    score_scale: float = Field(default=1.0, ge=0.0, le=1.0)
    matched_by_prefix: str = ""


def normalize_search_text(value: Any) -> str:
    """Apply only Skill-neutral Unicode and punctuation normalization."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    normalized = normalized.rstrip("。.!！?？")
    compact = "".join(character for character in normalized if not character.isspace())
    return "".join(
        character
        for character in compact
        if character.isalnum()
        or "ぁ" <= character <= "ヿ"
        or "一" <= character <= "龯"
    )


class SearchEngine:
    """Replaceable rule-based implementation of the common search boundary."""

    def search(
        self,
        query: str | Iterable[SearchTerm],
        documents: Iterable[SearchDocument],
    ) -> list[EntityCandidate]:
        terms = self._terms(query)
        if not terms:
            return []

        candidates: list[EntityCandidate] = []
        for document in documents:
            candidate = self._score_document(document, terms)
            if candidate is not None:
                candidates.append(candidate)

        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                normalize_search_text(candidate.entity.label),
                candidate.entity.entity_id,
            ),
        )

    def _terms(self, query: str | Iterable[SearchTerm]) -> tuple[SearchTerm, ...]:
        if isinstance(query, str):
            normalized = normalize_search_text(query)
            return (SearchTerm(value=normalized),) if normalized else ()

        terms: list[SearchTerm] = []
        seen: set[tuple[str, float, str]] = set()
        for raw_term in query:
            if not isinstance(raw_term, SearchTerm):
                continue
            value = normalize_search_text(raw_term.value)
            key = (value, raw_term.score_scale, raw_term.matched_by_prefix)
            if value and key not in seen:
                seen.add(key)
                terms.append(raw_term.model_copy(update={"value": value}))
        return tuple(terms)

    def _score_document(
        self,
        document: SearchDocument,
        terms: tuple[SearchTerm, ...],
    ) -> EntityCandidate | None:
        if not isinstance(document, SearchDocument):
            return None
        entity = _entity_ref(document)
        if entity is None:
            return None

        signals: list[tuple[float, str]] = []
        for term in terms:
            term_matched = False
            for keyword in document.keywords:
                keyword_value = normalize_search_text(keyword.value)
                if not keyword_value or term.value not in keyword_value:
                    continue
                is_exact = term.value == keyword_value
                base_score = keyword.exact_score if is_exact else keyword.partial_score
                reason = (
                    keyword.exact_matched_by
                    if is_exact
                    else keyword.partial_matched_by
                ) or keyword.matched_by
                signals.append(
                    (
                        base_score * term.score_scale,
                        f"{term.matched_by_prefix}{reason}",
                    )
                )
                term_matched = True

            # document is the generic catch-all search text. Builders can use
            # keywords when a field requires a stronger or explainable signal.
            searchable_text = normalize_search_text(document.document)
            if not term_matched and term.value in searchable_text:
                signals.append(
                    (0.30 * term.score_scale, f"{term.matched_by_prefix}document")
                )

        if not signals:
            return None

        strongest = max(score for score, _ in signals)
        matched_by = list(dict.fromkeys(reason for _, reason in signals))
        score = min(1.0, strongest + 0.04 * (len(matched_by) - 1))
        return EntityCandidate(
            entity=entity,
            score=round(score, 4),
            matched_by=",".join(matched_by),
        )


def _entity_ref(document: SearchDocument) -> EntityRef | None:
    metadata = document.metadata
    skill_id = metadata.get("skill_id")
    entity_type = metadata.get("entity_type")
    source = metadata.get("source")
    if not all(isinstance(value, str) and value for value in (skill_id, entity_type, source)):
        return None
    try:
        return EntityRef(
            skill_id=skill_id,
            entity_type=entity_type,
            entity_id=document.id,
            label=document.label,
            source=source,
            verified_at=metadata.get("verified_at"),
        )
    except (TypeError, ValueError):
        return None
