from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .chat_core import EntityCandidate
from .travel_chat_adapter import RUNTIME_SOURCE, trip_entity_ref


_QUERY_EXPANSIONS = {
    "神戸": ("兵庫", "須磨"),
    "須磨": ("須磨シーワールド",),
    "シーワールド": ("須磨シーワールド", "水族館"),
    "apm": ("アンパンマン", "アンパンマンミュージアム"),
    "アンパンマン": ("apm", "アンパンマンミュージアム"),
}

_REQUEST_SUFFIXES = (
    "を開いてください",
    "開いてください",
    "を表示してください",
    "表示してください",
    "を見せてください",
    "見せてください",
    "を開いて",
    "開いて",
    "を表示して",
    "表示して",
    "を見せて",
    "見せて",
    "を開く",
    "開く",
)


def normalize_travel_query(query: str) -> str:
    """Normalize a natural-language Travel query without applying vocabulary rules."""
    if not isinstance(query, str):
        return ""
    value = unicodedata.normalize("NFKC", query).casefold().strip()
    value = value.rstrip("。.!！?？")
    compact = "".join(character for character in value if not character.isspace())
    for suffix in _REQUEST_SUFFIXES:
        normalized_suffix = unicodedata.normalize("NFKC", suffix).casefold()
        if compact.endswith(normalized_suffix):
            compact = compact[: -len(normalized_suffix)]
            break
    compact = compact.strip("「」『』\"'")
    return "".join(
        character
        for character in compact
        if character.isalnum()
        or "ぁ" <= character <= "ヿ"
        or "一" <= character <= "龯"
    )


def expand_travel_query(query: str) -> tuple[str, ...]:
    """Return a deliberately small set of auxiliary Travel search terms."""
    normalized = normalize_travel_query(query)
    expansions: list[str] = []
    for key, values in _QUERY_EXPANSIONS.items():
        if normalize_travel_query(key) not in normalized:
            continue
        for value in values:
            term = normalize_travel_query(value)
            if term and term not in expansions:
                expansions.append(term)
    return tuple(expansions)


class TravelSearchIndex:
    """Rule-based v0.1 index for Trip entities returned by Travel Runtime.

    The class owns Travel-specific document construction and ranking. Its public
    boundary can later be backed by BM25, FTS, or embeddings without changing the
    Chat Core candidate contract.
    """

    def search(
        self,
        query: str,
        trips: Iterable[dict[str, Any]],
    ) -> list[EntityCandidate]:
        normalized_query = normalize_travel_query(query)
        if not normalized_query:
            return []

        direct_terms = _direct_terms(normalized_query)
        expanded_terms = expand_travel_query(normalized_query)
        verified_at = datetime.now(timezone.utc)
        candidates: list[EntityCandidate] = []

        for trip in trips:
            candidate = self._score_trip(
                trip,
                direct_terms=direct_terms,
                expanded_terms=expanded_terms,
                verified_at=verified_at,
            )
            if candidate is not None:
                candidates.append(candidate)

        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                normalize_travel_query(candidate.entity.label),
                candidate.entity.entity_id,
            ),
        )

    def _score_trip(
        self,
        trip: Any,
        *,
        direct_terms: tuple[str, ...],
        expanded_terms: tuple[str, ...],
        verified_at: datetime,
    ) -> EntityCandidate | None:
        if not isinstance(trip, dict):
            return None
        trip_id = trip.get("id")
        title = trip.get("title")
        if not isinstance(trip_id, str) or not trip_id.strip():
            return None
        label = (
            title.strip()
            if isinstance(title, str) and title.strip()
            else trip_id.strip()
        )
        document = _trip_document(trip)

        signals: list[tuple[float, str]] = []
        for term in direct_terms:
            if term == document["title"]:
                signals.append((1.0, "title_exact"))
            elif term and term in document["title"]:
                signals.append((0.86, "title_partial"))
            if _matches(term, document["prefectures"]):
                signals.append((0.68, "prefectures"))
            if _matches(term, document["memo"]):
                signals.append((0.58, "memo"))
            if _matches(term, document["dates"]):
                signals.append((0.42, "date"))
            if _matches(term, document["outing_type"]):
                signals.append((0.40, "outing_type"))

        for term in expanded_terms:
            if _matches(term, document["title"]):
                signals.append((0.48, "query_expansion:title"))
            if _matches(term, document["prefectures"]):
                signals.append((0.40, "query_expansion:prefectures"))
            if _matches(term, document["memo"]):
                signals.append((0.32, "query_expansion:memo"))

        if not signals:
            return None

        strongest = max(score for score, _ in signals)
        matched_by = list(dict.fromkeys(reason for _, reason in signals))
        score = min(1.0, strongest + 0.04 * (len(matched_by) - 1))
        return EntityCandidate(
            entity=trip_entity_ref(
                trip_id.strip(),
                label=label,
                source=RUNTIME_SOURCE,
                verified_at=verified_at,
            ),
            score=round(score, 4),
            matched_by=",".join(matched_by),
        )


def _direct_terms(normalized_query: str) -> tuple[str, ...]:
    terms = [normalized_query]
    reduced = normalized_query
    if reduced.endswith("の旅行"):
        reduced = reduced[: -len("の旅行")]
    elif reduced.endswith("旅行") and reduced != "旅行":
        reduced = reduced[: -len("旅行")]
    if reduced and reduced not in terms:
        terms.append(reduced)
    return tuple(terms)


def _trip_document(trip: dict[str, Any]) -> dict[str, str]:
    return {
        "title": _normalize_field(trip.get("title")),
        "prefectures": _normalize_field(trip.get("prefectures")),
        "memo": _normalize_field(trip.get("memo")),
        "dates": _normalize_field(
            (trip.get("start_date"), trip.get("end_date"))
        ),
        "outing_type": _normalize_field(trip.get("outing_type")),
    }


def _normalize_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return normalize_travel_query(str(value))


def _matches(term: str, field: str) -> bool:
    return bool(term and field and term in field)
