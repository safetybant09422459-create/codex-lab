from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Protocol

from .travel_storage import SQLiteTravelStorage

JST = timezone(timedelta(hours=9))


class TravelSource(Protocol):
    def get_trips(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def create_trip(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def create_timeline_item(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def set_trip_cover_image(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def set_spot_cover_image(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class PhotoCandidateProvider(Protocol):
    def get_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def thumbnail_url(self, asset_id: str) -> str:
        raise NotImplementedError


class PhotoRepositoryCandidateProvider:
    def __init__(self, repository: PhotoCandidateProvider | None = None) -> None:
        self.repository = repository

    def get_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        if self.repository is None:
            from .photo_repository import PhotoRepository

            self.repository = PhotoRepository()
        return self.repository.get_photos(from_at, to_at, limit, offset)

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        if self.repository is None:
            from .photo_repository import PhotoRepository

            self.repository = PhotoRepository()
        return self.repository.get_asset(asset_id)

    def thumbnail_url(self, asset_id: str) -> str:
        if self.repository is None:
            from .photo_repository import PhotoRepository

            self.repository = PhotoRepository()
        return self.repository.thumbnail_url(asset_id)


class TravelRepository:
    def __init__(
        self,
        source: TravelSource | None = None,
        photo_provider: PhotoCandidateProvider | None = None,
    ) -> None:
        self.source = source or SQLiteTravelStorage()
        self.photo_provider = photo_provider or PhotoRepositoryCandidateProvider()

    def get_trips(self) -> list[dict[str, Any]]:
        return self.source.get_trips()

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        return self.source.get_trip(trip_id)

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return self.source.get_trip_timeline(trip_id)

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        return self.source.get_timeline_item(timeline_item_id)

    def get_trip_photos(
        self, trip_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        normalized_trip_id = self._required_text(trip_id, "trip_id")
        normalized_limit = self._limit(limit)
        normalized_offset = self._offset(offset)

        trip = self.get_trip(normalized_trip_id)
        if trip is None:
            raise ValueError("trip not found")

        from_at, to_at = self._trip_photo_range(trip)
        photos = self.photo_provider.get_photos(
            from_at=from_at.isoformat(),
            to_at=to_at.isoformat(),
            limit=normalized_limit,
            offset=normalized_offset,
        )
        return {
            "trip_id": normalized_trip_id,
            "photos": photos,
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "count": len(photos),
            },
        }

    def get_spot_photos(
        self, timeline_item_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        normalized_timeline_item_id = self._required_text(
            timeline_item_id, "timeline_item_id"
        )
        normalized_limit = self._limit(limit)
        normalized_offset = self._offset(offset)

        item = self.get_timeline_item(normalized_timeline_item_id)
        if item is None:
            raise ValueError("timeline item not found")

        from_at, to_at = self._spot_photo_range(item)
        photos = self.photo_provider.get_photos(
            from_at=from_at.isoformat(),
            to_at=to_at.isoformat(),
            limit=normalized_limit,
            offset=normalized_offset,
        )
        return {
            "timeline_item_id": normalized_timeline_item_id,
            "trip_id": self._required_text(item.get("trip_id"), "trip_id"),
            "photos": photos,
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "count": len(photos),
            },
        }

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

    def set_trip_cover_image(
        self,
        *,
        trip_id: str,
        asset_id: str,
        selected_by: str | None = None,
    ) -> dict[str, Any]:
        normalized_trip_id = self._required_text(trip_id, "trip_id")
        normalized_asset_id = self._required_text(asset_id, "asset_id")
        normalized_selected_by = self._optional_text(selected_by) or "admin"

        if self.get_trip(normalized_trip_id) is None:
            raise ValueError("trip not found")

        asset = self.photo_provider.get_asset(normalized_asset_id)
        confirmed_asset_id = self._required_text(
            asset.get("asset_id", normalized_asset_id), "asset_id"
        )
        cover_image = self.source.set_trip_cover_image(
            trip_id=normalized_trip_id,
            asset_id=confirmed_asset_id,
            selected_by=normalized_selected_by,
        )
        thumbnail_url = asset.get("thumbnail_url")
        if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
            thumbnail_url = self.photo_provider.thumbnail_url(confirmed_asset_id)
        return {
            "trip_id": normalized_trip_id,
            "cover_image_id": cover_image["id"],
            "asset_id": confirmed_asset_id,
            "thumbnail_url": thumbnail_url,
            "source": "local_travel_write",
        }

    def set_spot_cover_image(
        self,
        *,
        timeline_item_id: str,
        asset_id: str,
        selected_by: str | None = None,
    ) -> dict[str, Any]:
        normalized_timeline_item_id = self._required_text(
            timeline_item_id, "timeline_item_id"
        )
        normalized_asset_id = self._required_text(asset_id, "asset_id")
        normalized_selected_by = self._optional_text(selected_by) or "admin"

        asset = self.photo_provider.get_asset(normalized_asset_id)
        confirmed_asset_id = self._required_text(
            asset.get("asset_id", normalized_asset_id), "asset_id"
        )
        cover_image = self.source.set_spot_cover_image(
            timeline_item_id=normalized_timeline_item_id,
            asset_id=confirmed_asset_id,
            selected_by=normalized_selected_by,
        )
        thumbnail_url = asset.get("thumbnail_url")
        if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
            thumbnail_url = self.photo_provider.thumbnail_url(confirmed_asset_id)
        return {
            "timeline_item_id": normalized_timeline_item_id,
            "cover_image_id": cover_image["id"],
            "asset_id": confirmed_asset_id,
            "thumbnail_url": thumbnail_url,
            "source": "local_travel_write",
        }

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

    def _limit(self, value: Any) -> int:
        if value is None:
            return 50
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("limit must be an integer")
        if value < 1 or value > 100:
            raise ValueError("limit must be between 1 and 100")
        return value

    def _offset(self, value: Any) -> int:
        if value is None:
            return 0
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("offset must be an integer")
        if value < 0:
            raise ValueError("offset must be greater than or equal to 0")
        return value

    def _trip_photo_range(self, trip: dict[str, Any]) -> tuple[datetime, datetime]:
        start_value = self._optional_text(trip.get("start_date"))
        end_value = self._optional_text(trip.get("end_date")) or start_value
        if start_value is None or end_value is None:
            raise ValueError("trip start_date and end_date are required")

        start_at = self._trip_boundary(start_value, is_end=False)
        end_at = self._trip_boundary(end_value, is_end=True)
        if end_at <= start_at:
            raise ValueError("trip end_date must be after start_date")
        return start_at, end_at

    def _trip_boundary(self, value: str, *, is_end: bool) -> datetime:
        if "T" in value:
            parsed = self._iso_datetime(value)
            if parsed.second != 0 or parsed.microsecond != 0:
                raise ValueError("trip datetime boundaries must be minute-aligned")
            return parsed

        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("trip dates must be ISO8601 dates or datetimes") from exc

        boundary_time = time(23, 59) if is_end else time(0, 0)
        return datetime.combine(parsed_date, boundary_time, JST)

    def _iso_datetime(self, value: str) -> datetime:
        normalized = value
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("trip datetimes must be ISO8601") from exc

        if parsed.tzinfo is None:
            raise ValueError("trip datetimes must include timezone")
        return parsed

    def _spot_photo_range(self, item: dict[str, Any]) -> tuple[datetime, datetime]:
        start_value = self._optional_text(item.get("start_at"))
        if start_value is None:
            raise ValueError("timeline item start_at is required")

        start_at = self._minute_aligned_datetime(start_value, "start_at")
        end_value = self._optional_text(item.get("end_at"))
        if end_value is None:
            end_at = start_at + timedelta(hours=2)
        else:
            end_at = self._minute_aligned_datetime(end_value, "end_at")

        if end_at <= start_at:
            raise ValueError("timeline item end_at must be after start_at")
        return start_at, end_at

    def _minute_aligned_datetime(self, value: str, field_name: str) -> datetime:
        normalized = value
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"timeline item {field_name} must be an ISO8601 datetime with timezone"
            ) from exc

        if parsed.tzinfo is None:
            raise ValueError(f"timeline item {field_name} must include timezone")
        return parsed.replace(second=0, microsecond=0)
