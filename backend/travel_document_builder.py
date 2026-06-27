from __future__ import annotations

from datetime import datetime
from typing import Any

from .search_engine import SearchDocument, SearchKeyword, normalize_search_text
from .travel_chat_adapter import (
    RUNTIME_SOURCE,
    TRAVEL_SKILL_ID,
    TRIP_ENTITY_TYPE,
)


class TravelDocumentBuilder:
    """Convert Runtime Trip values into the common SearchDocument contract."""

    def build(
        self,
        trip: Any,
        *,
        verified_at: datetime | None = None,
    ) -> SearchDocument | None:
        if not isinstance(trip, dict):
            return None
        trip_id = trip.get("id")
        if not isinstance(trip_id, str) or not trip_id.strip():
            return None
        title = trip.get("title")
        label = title.strip() if isinstance(title, str) and title.strip() else trip_id.strip()

        fields = {
            "title": _normalize_field(title),
            "prefectures": _normalize_field(trip.get("prefectures")),
            "memo": _normalize_field(trip.get("memo")),
            "date": _normalize_field((trip.get("start_date"), trip.get("end_date"))),
            "outing_type": _normalize_field(trip.get("outing_type")),
        }
        keywords = tuple(
            SearchKeyword(
                value=fields[name],
                matched_by=name,
                exact_matched_by=exact_matched_by,
                partial_matched_by=partial_matched_by,
                exact_score=exact_score,
                partial_score=partial_score,
            )
            for name, exact_score, partial_score, exact_matched_by, partial_matched_by in (
                ("title", 1.0, 0.86, "title_exact", "title_partial"),
                ("prefectures", 0.68, 0.68, None, None),
                ("memo", 0.58, 0.58, None, None),
                ("date", 0.42, 0.42, None, None),
                ("outing_type", 0.40, 0.40, None, None),
            )
            if fields[name]
        )
        return SearchDocument(
            id=trip_id.strip(),
            label=label,
            document=" ".join(value for value in fields.values() if value),
            metadata={
                "skill_id": TRAVEL_SKILL_ID,
                "entity_type": TRIP_ENTITY_TYPE,
                "source": RUNTIME_SOURCE,
                "verified_at": verified_at,
                "trip": dict(trip),
            },
            keywords=keywords,
        )

    def build_many(
        self,
        trips: Any,
        *,
        verified_at: datetime | None = None,
    ) -> list[SearchDocument]:
        documents: list[SearchDocument] = []
        for trip in trips:
            document = self.build(trip, verified_at=verified_at)
            if document is not None:
                documents.append(document)
        return documents


def _normalize_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value if item is not None)
    return normalize_search_text(value)
