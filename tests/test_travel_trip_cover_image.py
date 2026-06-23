import unittest
from typing import Any

from backend.travel_repository import TravelRepository


class FakeTravelSource:
    def __init__(self, trip: dict[str, Any] | None) -> None:
        self.trip = trip

    def get_trips(self) -> list[dict[str, Any]]:
        return []

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        if self.trip is not None and self.trip["id"] == trip_id:
            return dict(self.trip)
        return None

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        return []

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
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
    def get_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def thumbnail_url(self, asset_id: str) -> str:
        return f"/api/photo/assets/{asset_id}/thumbnail"


class GetTripCoverImageTest(unittest.TestCase):
    def test_adds_thumbnail_url_for_saved_photo_asset_cover(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "trip_1",
                    "title": "福岡旅行",
                    "cover_image": {
                        "id": "cover_1",
                        "image_source": "photo_asset",
                        "image_ref": "asset_1",
                    },
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        trip = repository.get_trip("trip_1")

        self.assertIsNotNone(trip)
        assert trip is not None
        self.assertEqual(
            trip["cover_image"]["thumbnail_url"],
            "/api/photo/assets/asset_1/thumbnail",
        )
        self.assertEqual(trip["cover_image"]["asset_id"], "asset_1")

    def test_trip_without_cover_image_stays_plain(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource({"id": "trip_1", "title": "福岡旅行"}),
            photo_provider=FakePhotoProvider(),
        )

        trip = repository.get_trip("trip_1")

        self.assertIsNotNone(trip)
        assert trip is not None
        self.assertNotIn("cover_image", trip)


if __name__ == "__main__":
    unittest.main()
