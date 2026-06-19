from typing import Any

from .executors import BaseExecutor
from .travel_repository import TravelRepository


class TravelExecutor(BaseExecutor):
    execution_mode = "local_travel_read"

    def __init__(self, repository: TravelRepository | None = None) -> None:
        self.repository = repository or TravelRepository()

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        if tool.id == "get_trips":
            return {
                "tool_id": tool.id,
                "trips": self.repository.get_trips(),
                "source": self.execution_mode,
            }

        if tool.id == "get_trip":
            trip_id = self._trip_id(params)
            return {
                "tool_id": tool.id,
                "trip": self.repository.get_trip(trip_id),
                "source": self.execution_mode,
            }

        if tool.id == "get_trip_timeline":
            trip_id = self._trip_id(params)
            return {
                "tool_id": tool.id,
                "trip_id": trip_id,
                "items": self.repository.get_trip_timeline(trip_id),
                "source": self.execution_mode,
            }

        raise ValueError(f"Unsupported travel tool: {tool.id}")

    def _trip_id(self, params: dict[str, Any]) -> str:
        trip_id = params.get("trip_id")
        if isinstance(trip_id, str) and trip_id.strip():
            return trip_id.strip()
        raise ValueError("trip_id is required")
