from typing import Any, Protocol

from .travel_sources import InMemoryTravelSource


class TravelSource(Protocol):
    def get_trips(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class TravelRepository:
    def __init__(self, source: TravelSource | None = None) -> None:
        self.source = source or InMemoryTravelSource()

    def get_trips(self) -> list[dict[str, Any]]:
        return self.source.get_trips()

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        return self.source.get_trip(trip_id)

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return self.source.get_trip_timeline(trip_id)
