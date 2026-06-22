import unittest
from typing import Any

from backend.travel_repository import TravelRepository


class FakeTravelSource:
    def __init__(self, item: dict[str, Any] | None) -> None:
        self.item = item

    def get_trips(self) -> list[dict[str, Any]]:
        return []

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        return None

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return []

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        if self.item is not None and self.item["id"] == timeline_item_id:
            return self.item
        return None

    def create_trip(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def create_timeline_item(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def set_trip_cover_image(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def set_spot_cover_image(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class FakePhotoProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {"from_at": from_at, "to_at": to_at, "limit": limit, "offset": offset}
        )
        return [
            {
                "asset_id": "asset_1",
                "taken_at": from_at,
                "thumbnail_url": "/api/photo/assets/asset_1/thumbnail",
                "source": "immich",
            }
        ]

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def thumbnail_url(self, asset_id: str) -> str:
        return f"/api/photo/assets/{asset_id}/thumbnail"


class GetSpotPhotosTest(unittest.TestCase):
    def test_uses_timeline_item_range_and_returns_photo_payload(self) -> None:
        provider = FakePhotoProvider()
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "start_at": "2026-04-02T10:00:30+09:00",
                    "end_at": "2026-04-02T12:15:59+09:00",
                }
            ),
            photo_provider=provider,
        )

        result = repository.get_spot_photos("item_1", limit=25, offset=5)

        self.assertEqual(result["timeline_item_id"], "item_1")
        self.assertEqual(result["trip_id"], "trip_1")
        self.assertEqual(result["pagination"], {"limit": 25, "offset": 5, "count": 1})
        self.assertEqual(result["photos"][0]["asset_id"], "asset_1")
        self.assertEqual(
            provider.calls,
            [
                {
                    "from_at": "2026-04-02T10:00:00+09:00",
                    "to_at": "2026-04-02T12:15:00+09:00",
                    "limit": 25,
                    "offset": 5,
                }
            ],
        )

    def test_end_at_defaults_to_two_hours_after_start_at(self) -> None:
        provider = FakePhotoProvider()
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "start_at": "2026-04-02T10:00:00+09:00",
                    "end_at": None,
                }
            ),
            photo_provider=provider,
        )

        repository.get_spot_photos("item_1")

        self.assertEqual(provider.calls[0]["to_at"], "2026-04-02T12:00:00+09:00")

    def test_missing_start_at_fails(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {"id": "item_1", "trip_id": "trip_1", "start_at": None}
            ),
            photo_provider=FakePhotoProvider(),
        )

        with self.assertRaisesRegex(ValueError, "timeline item start_at is required"):
            repository.get_spot_photos("item_1")

    def test_missing_timeline_item_fails(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(None),
            photo_provider=FakePhotoProvider(),
        )

        with self.assertRaisesRegex(ValueError, "timeline item not found"):
            repository.get_spot_photos("item_1")


if __name__ == "__main__":
    unittest.main()
