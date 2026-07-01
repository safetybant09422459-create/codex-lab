from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .rag_core import RagDocument
from .travel_repository import TravelRepository
from .travel_storage import SQLiteTravelStorage


class TravelRagDocumentBuilder:
    """Project canonical Travel records into Skill-neutral recall documents."""

    def build_trip(
        self,
        trip: dict[str, Any],
        timeline: list[dict[str, Any]],
    ) -> RagDocument | None:
        trip_id = _text(trip.get("id"))
        if not trip_id:
            return None
        timeline_text = " ".join(_item_text(item) for item in timeline)
        text = _join(
            trip.get("title"),
            trip.get("start_date"),
            trip.get("end_date"),
            trip.get("prefectures"),
            trip.get("outing_type"),
            trip.get("memo"),
            _travel_recall_terms(trip),
            timeline_text,
        )
        if not text:
            return None
        return RagDocument(
            id=f"travel:trip:{trip_id}",
            source_skill="travel",
            entity_type="trip",
            entity_id=trip_id,
            text=text,
            metadata={
                "start_date": trip.get("start_date"),
                "end_date": trip.get("end_date"),
                "prefectures": trip.get("prefectures"),
                "outing_type": trip.get("outing_type"),
                "status": trip.get("status"),
                "timeline_item_count": len(timeline),
                "canonical_source": "travel_repository",
            },
            visibility=_visibility(trip),
            updated_at=_updated_at(trip),
        )

    def build_experience(
        self,
        trip: dict[str, Any],
        item: dict[str, Any],
    ) -> RagDocument | None:
        item_id = _text(item.get("experience_id") or item.get("id"))
        trip_id = _text(trip.get("id") or item.get("trip_id"))
        if not item_id or not trip_id:
            return None
        text = _join(
            trip.get("title"),
            trip.get("prefectures"),
            _travel_recall_terms(trip),
            _day_label(trip.get("start_date"), item.get("start_at")),
            _item_text(item),
        )
        if not text:
            return None
        return RagDocument(
            id=f"travel:experience:{item_id}",
            source_skill="travel",
            entity_type="experience",
            entity_id=item_id,
            text=text,
            metadata={
                "trip_id": trip_id,
                "item_type": item.get("experience_type") or item.get("item_type"),
                "place_id": item.get("place_id"),
                "category": item.get("category"),
                "start_at": item.get("start_at"),
                "end_at": item.get("end_at"),
                "status": item.get("status"),
                "canonical_source": "travel_repository",
            },
            visibility=_visibility(trip),
            updated_at=_updated_at(item, fallback=_updated_at(trip)),
        )

    def build_many(
        self,
        trips: list[dict[str, Any]],
        timelines: dict[str, list[dict[str, Any]]],
    ) -> list[RagDocument]:
        documents: list[RagDocument] = []
        for trip in trips:
            trip_id = _text(trip.get("id"))
            timeline = timelines.get(trip_id, [])
            trip_document = self.build_trip(trip, timeline)
            if trip_document is not None:
                documents.append(trip_document)
            for item in timeline:
                document = self.build_experience(trip, item)
                if document is not None:
                    documents.append(document)
        return documents


class TravelRagProvider:
    def __init__(
        self,
        repository: TravelRepository | None = None,
        builder: TravelRagDocumentBuilder | None = None,
    ) -> None:
        # Activation is a read path. The canonical Runtime owns schema setup.
        self.repository = repository or TravelRepository(
            source=SQLiteTravelStorage(initialize=False)
        )
        self.builder = builder or TravelRagDocumentBuilder()

    def documents(self) -> list[RagDocument]:
        trips = self.repository.get_trips()
        timelines = {
            str(trip["id"]): self.repository.get_trip_timeline(str(trip["id"]))
            for trip in trips
            if trip.get("id")
        }
        return self.builder.build_many(trips, timelines)


def _item_text(item: dict[str, Any]) -> str:
    return _join(
        item.get("display_title"),
        item.get("place_name"),
        item.get("category"),
        item.get("memo"),
        item.get("start_at"),
    )


def _join(*values: Any) -> str:
    return " ".join(value for raw in values if (value := _text(raw)))


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _visibility(trip: dict[str, Any]) -> str:
    return _text(trip.get("privacy_level")) or "private"


def _travel_recall_terms(trip: dict[str, Any]) -> str:
    """Travel-owned v0.1 aliases; future approved Enrichment replaces these."""
    prefectures = _text(trip.get("prefectures"))
    aliases: list[str] = []
    if "兵庫" in prefectures:
        aliases.append("神戸")
    return " ".join(aliases)


def _updated_at(value: dict[str, Any], fallback: datetime | None = None) -> datetime:
    raw = value.get("updated_at")
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback or datetime.now(timezone.utc)


def _day_label(start_date: Any, start_at: Any) -> str:
    try:
        trip_start = datetime.fromisoformat(str(start_date)).date()
        item_date = datetime.fromisoformat(str(start_at).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return ""
    day = (item_date - trip_start).days + 1
    return f"{day}日目" if day >= 1 else ""
