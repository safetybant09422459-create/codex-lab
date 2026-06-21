from datetime import datetime
from typing import Any

from .executors import BaseExecutor
from .photo_repository import PhotoRepository


class PhotoExecutor(BaseExecutor):
    execution_mode = "local_photo_read"

    def __init__(self, repository: PhotoRepository | None = None) -> None:
        self.repository = repository or PhotoRepository()

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        if tool.id == "get_asset":
            return self._get_asset(tool.id, params)
        if tool.id == "get_photos":
            return self._get_photos(tool.id, params)
        raise ValueError(f"Unsupported photo tool: {tool.id}")

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
