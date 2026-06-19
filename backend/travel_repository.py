from typing import Any, Protocol

from .travel_storage import SQLiteTravelStorage


class TravelSource(Protocol):
    def get_trips(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def create_trip(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def create_timeline_item(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class TravelRepository:
    def __init__(self, source: TravelSource | None = None) -> None:
        self.source = source or SQLiteTravelStorage()

    def get_trips(self) -> list[dict[str, Any]]:
        return self.source.get_trips()

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        return self.source.get_trip(trip_id)

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return self.source.get_trip_timeline(trip_id)

    def create_trip(
        self,
        *,
        title: str,
        start_date: str | None = None,
        end_date: str | None = None,
        outing_type: str | None = None,
        prefectures: Any = None,
        memo: str | None = None,
        privacy_level: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        normalized_title = self._required_text(title, "title")
        return self.source.create_trip(
            title=normalized_title,
            start_date=self._optional_text(start_date),
            end_date=self._optional_text(end_date),
            outing_type=self._optional_text(outing_type),
            prefectures=prefectures,
            memo=self._optional_text(memo),
            privacy_level=self._optional_text(privacy_level) or "private",
            created_by=self._optional_text(created_by),
        )

    def create_timeline_item(
        self,
        *,
        trip_id: str,
        item_type: str,
        display_title: str,
        place_name: str | None = None,
        place_id: str | None = None,
        category: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        time_kind: str | None = None,
        memo: str | None = None,
        order_no: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        return self.source.create_timeline_item(
            trip_id=self._required_text(trip_id, "trip_id"),
            item_type=self._required_text(item_type, "item_type"),
            display_title=self._required_text(display_title, "display_title"),
            place_name=self._optional_text(place_name),
            place_id=self._optional_text(place_id),
            category=self._optional_text(category),
            start_at=self._optional_text(start_at),
            end_at=self._optional_text(end_at),
            time_kind=self._optional_text(time_kind),
            memo=self._optional_text(memo),
            order_no=order_no,
            status=self._optional_text(status) or "planned",
        )

    def _required_text(self, value: Any, field_name: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        raise ValueError(f"{field_name} is required")

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return str(value)
