from datetime import datetime
from typing import Any

from .executors import BaseExecutor
from .photo_repository import PhotoRepository


class PhotoExecutor(BaseExecutor):
    execution_mode = "local_photo_read"

    def __init__(self, repository: PhotoRepository | None = None) -> None:
        self.repository = repository or PhotoRepository()

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        if tool.id != "get_photos":
            raise ValueError(f"Unsupported photo tool: {tool.id}")

        from_at = self._iso_datetime(params.get("from"), "from")
        to_at = self._iso_datetime(params.get("to"), "to")
        if to_at <= from_at:
            raise ValueError("to must be after from")

        limit = self._limit(params.get("limit"))
        return {
            "tool_id": tool.id,
            "photos": self.repository.get_photos(
                from_at=from_at.isoformat(),
                to_at=to_at.isoformat(),
                limit=limit,
            ),
            "source": "immich",
        }

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
        return min(max(value, 1), 1000)
