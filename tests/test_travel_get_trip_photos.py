import unittest
from typing import Any

from fastapi import HTTPException

from backend import main
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
                "preview_url": "/api/photo/assets/asset_1/preview",
                "source": "immich",
            }
        ]

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def thumbnail_url(self, asset_id: str) -> str:
        return f"/api/photo/assets/{asset_id}/thumbnail"


class GetTripPhotosTest(unittest.TestCase):
    def test_uses_trip_date_range_and_returns_photo_payload(self) -> None:
        provider = FakePhotoProvider()
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "trip_1",
                    "title": "福岡旅行",
                    "start_date": "2026-04-02",
                    "end_date": "2026-04-03",
                }
            ),
            photo_provider=provider,
        )

        result = repository.get_trip_photos("trip_1", limit=20, offset=0)

        self.assertEqual(result["trip_id"], "trip_1")
        self.assertEqual(
            result["pagination"],
            {"limit": 20, "offset": 0, "count": 1, "has_more": False},
        )
        self.assertEqual(result["photos"][0]["asset_id"], "asset_1")
        self.assertEqual(
            provider.calls,
            [
                {
                    "from_at": "2026-04-02T00:00:00+09:00",
                    "to_at": "2026-04-03T23:59:00+09:00",
                    "limit": 20,
                    "offset": 0,
                }
            ],
        )

    def test_missing_trip_fails(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(None),
            photo_provider=FakePhotoProvider(),
        )

        with self.assertRaisesRegex(ValueError, "trip not found"):
            repository.get_trip_photos("trip_1", limit=20)


class FakeRuntimeService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def execute_stub(
        self,
        tool_id: str,
        params: dict[str, Any],
        confirmed: bool = False,
        role: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "tool_id": tool_id,
                "params": params,
                "confirmed": confirmed,
                "role": role,
            }
        )
        return self.response


class TravelPhotosApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_runtime_service = main.runtime_service

    def tearDown(self) -> None:
        main.runtime_service = self.original_runtime_service

    async def test_api_executes_trip_photos_with_admin_read_context(self) -> None:
        runtime_service = FakeRuntimeService(
            {
                "success": True,
                "result": {
                    "trip_id": "trip_1",
                    "photos": [
                        {
                            "asset_id": "asset_1",
                            "taken_at": "2026-04-02T00:00:00+09:00",
                            "thumbnail_url": "/api/photo/assets/asset_1/thumbnail",
                            "preview_url": "/api/photo/assets/asset_1/preview",
                            "source": "immich",
                        }
                    ],
                    "pagination": {"limit": 20, "offset": 0, "count": 1},
                    "source": "photo_skill",
                },
            }
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_trip_photos("trip_1", limit=100, offset=-3)

        self.assertEqual(response.trip_id, "trip_1")
        self.assertEqual(response.photos[0]["asset_id"], "asset_1")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "get_trip_photos",
                    "params": {"trip_id": "trip_1", "limit": 20, "offset": 0},
                    "confirmed": False,
                    "role": "admin",
                }
            ],
        )

    async def test_api_maps_permission_denied_to_403(self) -> None:
        main.runtime_service = FakeRuntimeService(
            {
                "success": False,
                "result": None,
                "blocked": True,
                "permission_denied": True,
                "reason": "guest is only allowed to execute read low risk tools",
            }
        )

        with self.assertRaises(HTTPException) as context:
            await main.travel_get_trip_photos("trip_1", limit=20, offset=0)

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail,
            "guest is only allowed to execute read low risk tools",
        )


if __name__ == "__main__":
    unittest.main()
