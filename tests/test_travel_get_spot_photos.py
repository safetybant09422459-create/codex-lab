import unittest
from typing import Any

from fastapi import HTTPException

from backend import main
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
    def test_get_spot_returns_timeline_item(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "display_title": "アンパンマンミュージアム1日目",
                    "start_at": "2026-04-02T10:00:00+09:00",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        result = repository.get_spot("item_1")

        self.assertIsNotNone(result)
        self.assertEqual(result["display_title"], "アンパンマンミュージアム1日目")

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


class FakeRuntimeService:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
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
        return self.responses.pop(0)


class TravelSpotApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_runtime_service = main.runtime_service

    def tearDown(self) -> None:
        main.runtime_service = self.original_runtime_service

    async def test_api_executes_spot_and_spot_photos_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "timeline_item_id": "item_1",
                        "spot": {
                            "id": "item_1",
                            "trip_id": "trip_1",
                            "display_title": "アンパンマンミュージアム1日目",
                            "start_at": "2026-04-02T10:00:00+09:00",
                            "end_at": "2026-04-02T12:00:00+09:00",
                            "memo": "初日",
                        },
                        "source": "local_travel_read",
                    },
                },
                {
                    "success": True,
                    "result": {
                        "timeline_item_id": "item_1",
                        "trip_id": "trip_1",
                        "photos": [
                            {
                                "asset_id": "asset_1",
                                "taken_at": "2026-04-02T10:00:00+09:00",
                                "thumbnail_url": "/api/photo/assets/asset_1/thumbnail",
                                "preview_url": "/api/photo/assets/asset_1/preview",
                                "source": "immich",
                            }
                        ],
                        "pagination": {"limit": 20, "offset": 0, "count": 1},
                        "source": "photo_skill",
                    },
                },
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_spot_detail("item_1", limit=100, offset=-1)

        self.assertEqual(response.spot["display_title"], "アンパンマンミュージアム1日目")
        self.assertEqual(response.photos[0]["asset_id"], "asset_1")
        self.assertFalse(response.photo_error)
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "get_spot",
                    "params": {"timeline_item_id": "item_1"},
                    "confirmed": False,
                    "role": "guest",
                },
                {
                    "tool_id": "get_spot_photos",
                    "params": {"timeline_item_id": "item_1", "limit": 20, "offset": 0},
                    "confirmed": False,
                    "role": "admin",
                },
            ],
        )

    async def test_api_maps_missing_spot_to_404(self) -> None:
        main.runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "timeline_item_id": "item_1",
                        "spot": None,
                        "source": "local_travel_read",
                    },
                }
            ]
        )

        with self.assertRaises(HTTPException) as context:
            await main.travel_get_spot_detail("item_1", limit=20, offset=0)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Travel spot not found")

    async def test_api_returns_spot_when_photo_lookup_fails(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "timeline_item_id": "item_1",
                        "spot": {
                            "id": "item_1",
                            "trip_id": "trip_1",
                            "display_title": "アンパンマンミュージアム1日目",
                        },
                        "source": "local_travel_read",
                    },
                },
                {
                    "success": False,
                    "result": None,
                    "blocked": True,
                    "permission_denied": True,
                    "reason": "photo read denied",
                },
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_spot_detail("item_1", limit=20, offset=0)

        self.assertEqual(response.spot["id"], "item_1")
        self.assertEqual(response.photos, [])
        self.assertTrue(response.photo_error)


if __name__ == "__main__":
    unittest.main()
