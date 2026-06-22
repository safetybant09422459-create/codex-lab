from copy import deepcopy
from typing import Any


class InMemoryTravelSource:
    def __init__(self) -> None:
        self._trips = [
            {
                "id": "trip_suma_2026",
                "title": "須磨シーワールド",
                "start_date": "2026-05-08",
                "end_date": "2026-05-09",
                "outing_type": "overnight",
                "cover_image": "/static/sample/suma.jpg",
                "participants": ["パパ", "ママ", "結衣", "麻衣"],
            }
        ]
        self._timeline_items_by_trip_id = {
            "trip_suma_2026": [
                {
                    "id": "item_001",
                    "item_type": "spot",
                    "display_title": "オルカショーでずぶ濡れ",
                    "place_name": "須磨シーワールド",
                    "category": "観光",
                    "start_at": "2026-05-09T10:00",
                    "end_at": "2026-05-09T13:00",
                    "cover_image": "/static/sample/orca.jpg",
                    "memo": "家族のおでかけ記憶Skillのサンプル",
                    "participants": ["パパ", "ママ", "結衣", "麻衣"],
                    "linked_photos": [],
                },
                {
                    "id": "item_002",
                    "item_type": "event",
                    "display_title": "初めての海",
                    "place_name": None,
                    "category": "観光",
                    "start_at": "2026-05-09T15:00",
                    "end_at": "2026-05-09T16:30",
                    "cover_image": "/static/sample/sea.jpg",
                    "memo": "",
                    "participants": ["パパ", "ママ", "結衣", "麻衣"],
                    "linked_photos": [],
                },
            ]
        }

    def get_trips(self) -> list[dict[str, Any]]:
        return deepcopy(self._trips)

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        for trip in self._trips:
            if trip["id"] == trip_id:
                return deepcopy(trip)
        return None

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._timeline_items_by_trip_id.get(trip_id, []))

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        for items in self._timeline_items_by_trip_id.values():
            for item in items:
                if item["id"] == timeline_item_id:
                    return deepcopy(item)
        return None
