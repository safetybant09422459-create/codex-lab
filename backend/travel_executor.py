from typing import Any

from .executors import BaseExecutor
from .travel_repository import TravelRepository


class TravelExecutor(BaseExecutor):
    def __init__(self, repository: TravelRepository | None = None) -> None:
        self.repository = repository or TravelRepository()

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        if tool.id == "get_trips":
            return {
                "tool_id": tool.id,
                "trips": self.repository.get_trips(),
                "source": "local_travel_read",
            }

        if tool.id == "get_trip":
            trip_id = self._trip_id(params)
            return {
                "tool_id": tool.id,
                "trip": self.repository.get_trip(trip_id),
                "source": "local_travel_read",
            }

        if tool.id == "get_trip_timeline":
            trip_id = self._trip_id(params)
            return {
                "tool_id": tool.id,
                "trip_id": trip_id,
                "items": self.repository.get_trip_timeline(trip_id),
                "source": "local_travel_read",
            }

        if tool.id == "get_spot":
            timeline_item_id = self._timeline_item_id(params)
            return {
                "tool_id": tool.id,
                "timeline_item_id": timeline_item_id,
                "spot": self.repository.get_spot(timeline_item_id),
                "source": "local_travel_read",
            }

        if tool.id == "get_trip_photos":
            trip_id = self._trip_id(params)
            return {
                "tool_id": tool.id,
                **self.repository.get_trip_photos(
                    trip_id,
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if tool.id == "get_spot_photos":
            timeline_item_id = self._timeline_item_id(params)
            return {
                "tool_id": tool.id,
                **self.repository.get_spot_photos(
                    timeline_item_id,
                    limit=params.get("limit", 50),
                    offset=params.get("offset", 0),
                ),
                "source": "photo_skill",
            }

        if tool.id == "create_trip":
            return {
                "tool_id": tool.id,
                "trip": self.repository.create_trip(
                    title=params.get("title"),
                    start_date=params.get("start_date"),
                    end_date=params.get("end_date"),
                    outing_type=params.get("outing_type"),
                    prefectures=params.get("prefectures"),
                    memo=params.get("memo"),
                    privacy_level=params.get("privacy_level"),
                    created_by=params.get("created_by"),
                ),
                "source": "local_travel_write",
            }

        if tool.id == "create_timeline_item":
            return {
                "tool_id": tool.id,
                "item": self.repository.create_timeline_item(
                    trip_id=params.get("trip_id"),
                    item_type=params.get("item_type"),
                    display_title=params.get("display_title"),
                    place_name=params.get("place_name"),
                    place_id=params.get("place_id"),
                    category=params.get("category"),
                    start_at=params.get("start_at"),
                    end_at=params.get("end_at"),
                    time_kind=params.get("time_kind"),
                    memo=params.get("memo"),
                    order_no=params.get("order_no"),
                    status=params.get("status"),
                ),
                "source": "local_travel_write",
            }

        if tool.id == "set_trip_cover_image":
            return {
                "tool_id": tool.id,
                **self.repository.set_trip_cover_image(
                    trip_id=params.get("trip_id"),
                    asset_id=params.get("asset_id"),
                    selected_by="admin",
                ),
            }

        if tool.id == "set_spot_cover_image":
            return {
                "tool_id": tool.id,
                **self.repository.set_spot_cover_image(
                    timeline_item_id=params.get("timeline_item_id"),
                    asset_id=params.get("asset_id"),
                    selected_by="admin",
                ),
            }

        raise ValueError(f"Unsupported travel tool: {tool.id}")

    @property
    def execution_mode(self) -> str:
        return "local_travel_read"

    def get_execution_mode(self, tool: Any) -> str:
        if tool.id in {
            "create_trip",
            "create_timeline_item",
            "set_trip_cover_image",
            "set_spot_cover_image",
        }:
            return "local_travel_write"
        return "local_travel_read"

    def _trip_id(self, params: dict[str, Any]) -> str:
        trip_id = params.get("trip_id")
        if isinstance(trip_id, str) and trip_id.strip():
            return trip_id.strip()
        raise ValueError("trip_id is required")

    def _timeline_item_id(self, params: dict[str, Any]) -> str:
        timeline_item_id = params.get("timeline_item_id")
        if isinstance(timeline_item_id, str) and timeline_item_id.strip():
            return timeline_item_id.strip()
        raise ValueError("timeline_item_id is required")
