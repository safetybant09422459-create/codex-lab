from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from .domain_provider import DomainProvider, OperationContext, ProviderOperationSpec
from .executors import BaseExecutor
from .photo_immich_adapter import ImmichAPIError, ImmichConfigurationError
from .photo_repository import PhotoRepository


class PhotoProvider(DomainProvider):
    """Read-only Photo capability boundary backed by Immich metadata."""

    provider_id = "photo"

    def __init__(
        self,
        repository: PhotoRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or PhotoRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        return (
            ProviderOperationSpec(
                operation_id="get_recent_photos",
                what_it_can_do=(
                    "Return recent photo metadata facts from Immich, including "
                    "daily and camera counts, observed date range, location/face "
                    "metadata counts, and a small sample of asset IDs."
                ),
                what_it_cannot_do=(
                    "It cannot display photos, choose photos for the user, identify "
                    "people, modify assets, or compose a conversational answer."
                ),
                examples=({"arguments": {}}, {"arguments": {"days": 7}}),
                limitations=(
                    "Photo display requires a future Presentation Contract.",
                    "Results are unavailable when Immich is not configured or reachable.",
                ),
            ),
        )

    def execute(
        self, operation: OperationContext, params: dict[str, Any]
    ) -> dict[str, Any]:
        if operation.operation_id == "get_recent_photos":
            return self._get_recent_photos(operation.operation_id, params)
        # Legacy Runtime tools remain available outside the Provider catalog.
        if operation.operation_id == "get_asset":
            return self._get_asset(operation.operation_id, params)
        if operation.operation_id == "get_photos":
            return self._get_photos(operation.operation_id, params)
        raise ValueError(f"Unsupported photo operation: {operation.operation_id}")

    def _get_recent_photos(
        self, operation_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        days = self._bounded_integer(params.get("days"), "days", 30, 1, 365)
        limit = self._bounded_integer(params.get("limit"), "limit", 20, 1, 100)
        observed_at = self._clock().astimezone(timezone.utc)
        from_at = observed_at - timedelta(days=days)
        requested_range = {
            "from": from_at.isoformat(),
            "to": observed_at.isoformat(),
        }
        try:
            photos = self.repository.get_photos(
                from_at=from_at.isoformat(),
                to_at=observed_at.isoformat(),
                limit=limit,
                offset=0,
            )
        except (ImmichConfigurationError, ImmichAPIError, OSError) as exc:
            return {
                "tool_id": operation_id,
                "photo_count": 0,
                "date_range": requested_range,
                "date_bucket_counts": {},
                "day_count": 0,
                "has_location": None,
                "has_faces": None,
                "has_location_count": 0,
                "has_faces_count": 0,
                "camera_make_counts": {},
                "camera_model_counts": {},
                "timezone": None,
                "newest_photo_at": None,
                "oldest_photo_at": None,
                "sample_photo_ids": [],
                "limitations": [
                    "Recent photo metadata could not be read from Immich.",
                    str(exc),
                    "Photo display is not supported in read-only v0.",
                ],
                "provenance": {"source": "unavailable"},
                "visibility": "family",
                "observed_at": observed_at.isoformat(),
                "source": "unavailable",
                "connection_status": "unavailable",
            }

        dated_photos = [
            (photo, parsed)
            for photo in photos
            if isinstance(photo, dict)
            and (parsed := self._parse_photo_datetime(photo.get("taken_at"))) is not None
        ]
        date_bucket_counts = Counter(
            parsed.date().isoformat() for _, parsed in dated_photos
        )
        sorted_dates = sorted(dated_photos, key=lambda item: item[1])
        oldest_photo_at = sorted_dates[0][0]["taken_at"] if sorted_dates else None
        newest_photo_at = sorted_dates[-1][0]["taken_at"] if sorted_dates else None
        date_range = requested_range
        if sorted_dates:
            date_range = {"from": oldest_photo_at, "to": newest_photo_at}
        timezones = sorted(
            {
                value
                for photo in photos
                if isinstance(photo, dict)
                and isinstance((value := photo.get("timezone")), str)
                and value
            }
        )
        return {
            "tool_id": operation_id,
            "photo_count": len(photos),
            "date_range": date_range,
            "date_bucket_counts": dict(sorted(date_bucket_counts.items())),
            "day_count": len(date_bucket_counts),
            "has_location": any(photo.get("has_location") is True for photo in photos),
            "has_faces": any(photo.get("has_faces") is True for photo in photos),
            "has_location_count": sum(
                photo.get("has_location") is True for photo in photos
            ),
            "has_faces_count": sum(photo.get("has_faces") is True for photo in photos),
            "camera_make_counts": self._text_counts(photos, "camera_make"),
            "camera_model_counts": self._text_counts(photos, "camera_model"),
            "timezone": timezones[0] if len(timezones) == 1 else None,
            "newest_photo_at": newest_photo_at,
            "oldest_photo_at": oldest_photo_at,
            "sample_photo_ids": [
                photo["asset_id"]
                for photo in photos[:5]
                if isinstance(photo.get("asset_id"), str)
            ],
            "limitations": [
                f"At most {limit} recent photo metadata records were inspected.",
                "Location and face flags only report metadata present in returned records.",
                "Photo display is not supported in read-only v0.",
            ],
            "provenance": {"source": "immich"},
            "visibility": "family",
            "observed_at": observed_at.isoformat(),
            "source": "immich",
            "connection_status": "available",
        }

    def _get_photos(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        from_at = self._iso_datetime(params.get("from"), "from")
        to_at = self._iso_datetime(params.get("to"), "to")
        if to_at <= from_at:
            raise ValueError("to must be after from")

        limit = self._limit(params.get("limit"))
        offset = self._offset(params.get("offset"))
        photos = self.repository.get_photos(
            from_at=from_at.isoformat(),
            to_at=to_at.isoformat(),
            limit=limit,
            offset=offset,
        )
        return {
            "tool_id": tool_id,
            "photos": photos,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(photos),
            },
            "source": "immich",
        }

    def _get_asset(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        asset_id = params.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id is required")
        asset = self.repository.get_asset(asset_id.strip())
        return {"tool_id": tool_id, **asset}

    def _iso_datetime(self, value: Any, field_name: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an ISO8601 datetime with timezone"
            ) from exc

        if parsed.tzinfo is None:
            raise ValueError(f"{field_name} must include timezone")
        if parsed.second != 0 or parsed.microsecond != 0:
            raise ValueError(f"{field_name} must be minute-aligned with seconds 00")
        return parsed

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

    @staticmethod
    def _bounded_integer(
        value: Any, field_name: str, default: int, minimum: int, maximum: int
    ) -> int:
        if value is None:
            return default
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer")
        if value < minimum or value > maximum:
            raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
        return value

    @staticmethod
    def _parse_photo_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None

    @staticmethod
    def _text_counts(photos: list[dict[str, Any]], field_name: str) -> dict[str, int]:
        counts = Counter(
            value
            for photo in photos
            if isinstance(photo, dict)
            and isinstance((value := photo.get(field_name)), str)
            and value
        )
        return dict(sorted(counts.items()))

    def get_execution_mode(self, operation: OperationContext) -> str:
        if operation.operation_id == "get_recent_photos":
            return "immich_photo_metadata_read"
        return "local_photo_read"

    def observation_details(
        self, operation: OperationContext, result: dict[str, Any]
    ) -> dict[str, Any]:
        if operation.operation_id != "get_recent_photos":
            return {"visibility": "family"}
        facts = {
            key: result.get(key)
            for key in (
                "photo_count",
                "date_range",
                "date_bucket_counts",
                "day_count",
                "has_location",
                "has_faces",
                "has_location_count",
                "has_faces_count",
                "camera_make_counts",
                "camera_model_counts",
                "timezone",
                "newest_photo_at",
                "oldest_photo_at",
                "source",
                "connection_status",
                "sample_photo_ids",
            )
        }
        return {
            "facts": facts,
            "counts": {"photo_count": int(result.get("photo_count", 0))},
            "limitations": list(result.get("limitations", [])),
            "visibility": str(result.get("visibility", "family")),
            "related_capabilities": ["review_recent_photo_metadata"],
        }


class PhotoExecutor(BaseExecutor):
    """Runtime adapter; Photo operation dispatch belongs to PhotoProvider."""

    execution_mode = "local_photo_read"

    def __init__(
        self,
        provider: PhotoProvider | None = None,
        repository: PhotoRepository | None = None,
    ) -> None:
        if provider is not None and repository is not None:
            raise ValueError("provider and repository are mutually exclusive")
        self.provider = provider or PhotoProvider(repository=repository)

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        return self.provider.execute(self._operation(tool), params)

    def get_execution_mode(self, tool: Any) -> str:
        return self.provider.get_execution_mode(self._operation(tool))

    @staticmethod
    def _operation(tool: Any) -> OperationContext:
        return OperationContext(
            operation_id=tool.id,
            skill_id=getattr(tool, "skill_id", "photo"),
            mode=getattr(tool, "mode", "read"),
            risk_level=getattr(tool, "risk_level", "low"),
        )
