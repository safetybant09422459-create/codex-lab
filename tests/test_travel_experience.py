import unittest
from types import SimpleNamespace
from typing import Any

from backend import main
from backend.travel_executor import TravelExecutor
from backend.travel_repository import TravelRepository


class FakeTravelSource:
    def __init__(self, item: dict[str, Any] | None = None) -> None:
        self.item = item
        self.created_kwargs: dict[str, Any] | None = None

    def get_trips(self) -> list[dict[str, Any]]:
        return []

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        return None

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        if self.item is None or self.item.get("trip_id") != trip_id:
            return []
        return [dict(self.item)]

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        if self.item is not None and self.item["id"] == timeline_item_id:
            return dict(self.item)
        return None

    def create_trip(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def create_timeline_item(self, **kwargs: Any) -> dict[str, Any]:
        self.created_kwargs = dict(kwargs)
        return {
            "id": "item_created",
            "trip_id": kwargs["trip_id"],
            "item_type": kwargs["item_type"],
            "display_title": kwargs["display_title"],
            "place_name": kwargs.get("place_name"),
            "place_id": kwargs.get("place_id"),
            "category": kwargs.get("category"),
            "start_at": kwargs.get("start_at"),
            "end_at": kwargs.get("end_at"),
            "time_kind": kwargs.get("time_kind"),
            "cover_image_id": None,
            "memo": kwargs.get("memo"),
            "order_no": kwargs.get("order_no"),
            "status": kwargs.get("status"),
            "created_at": "2026-06-23T10:00:00+09:00",
            "updated_at": "2026-06-23T10:00:00+09:00",
        }

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
        return [{"asset_id": "asset_1", "taken_at": from_at, "source": "immich"}]

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def thumbnail_url(self, asset_id: str) -> str:
        return f"/api/photo/assets/{asset_id}/thumbnail"


class ExperienceRepositoryTest(unittest.TestCase):
    def test_create_experience_stores_as_timeline_item_and_returns_aliases(self) -> None:
        source = FakeTravelSource()
        repository = TravelRepository(source=source, photo_provider=FakePhotoProvider())

        experience = repository.create_experience(
            trip_id="trip_1",
            experience_type="event",
            display_title="ショー",
            start_at="2026-04-02T13:00:00+09:00",
        )

        self.assertEqual(source.created_kwargs["item_type"], "event")
        self.assertEqual(experience["id"], "item_created")
        self.assertEqual(experience["experience_id"], "item_created")
        self.assertEqual(experience["timeline_item_id"], "item_created")
        self.assertEqual(experience["experience_type"], "event")
        self.assertEqual(experience["item_type"], "event")

    def test_get_experience_normalizes_existing_timeline_item(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "start_at": "2026-04-02T10:00:00+09:00",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        experience = repository.get_experience("item_1")

        self.assertIsNotNone(experience)
        assert experience is not None
        self.assertEqual(experience["experience_id"], "item_1")
        self.assertEqual(experience["timeline_item_id"], "item_1")
        self.assertEqual(experience["experience_type"], "spot")

    def test_get_experience_photos_returns_experience_and_legacy_ids(self) -> None:
        provider = FakePhotoProvider()
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "memo",
                    "display_title": "昼寝",
                    "start_at": "2026-04-02T14:00:00+09:00",
                    "end_at": "2026-04-02T15:00:00+09:00",
                }
            ),
            photo_provider=provider,
        )

        result = repository.get_experience_photos("item_1", limit=10, offset=2)

        self.assertEqual(result["experience_id"], "item_1")
        self.assertEqual(result["timeline_item_id"], "item_1")
        self.assertEqual(result["experience_type"], "memo")
        self.assertEqual(result["trip_id"], "trip_1")
        self.assertEqual(result["pagination"], {"limit": 10, "offset": 2, "count": 1})

    def test_legacy_spot_aliases_delegate_to_experience_boundary(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "start_at": "2026-04-02T10:00:00+09:00",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        spot = repository.get_spot("item_1")
        photos = repository.get_spot_photos("item_1")

        self.assertEqual(spot["experience_id"], "item_1")
        self.assertEqual(photos["experience_id"], "item_1")
        self.assertEqual(photos["timeline_item_id"], "item_1")


class ExperienceExecutorTest(unittest.TestCase):
    def test_executes_experience_tools(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "start_at": "2026-04-02T10:00:00+09:00",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )
        executor = TravelExecutor(repository=repository)

        get_result = executor.execute(
            SimpleNamespace(id="get_experience"), {"experience_id": "item_1"}
        )
        photos_result = executor.execute(
            SimpleNamespace(id="get_experience_photos"),
            {"experience_id": "item_1", "limit": 5, "offset": 0},
        )

        self.assertEqual(get_result["experience"]["experience_id"], "item_1")
        self.assertEqual(photos_result["experience_id"], "item_1")
        self.assertEqual(photos_result["timeline_item_id"], "item_1")


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


class TravelExperienceApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_runtime_service = main.runtime_service

    def tearDown(self) -> None:
        main.runtime_service = self.original_runtime_service

    async def test_api_executes_experience_and_photos_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "experience": {
                            "id": "item_1",
                            "experience_id": "item_1",
                            "timeline_item_id": "item_1",
                            "experience_type": "spot",
                            "item_type": "spot",
                            "trip_id": "trip_1",
                            "display_title": "水族館",
                        },
                        "source": "local_travel_read",
                    },
                },
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "timeline_item_id": "item_1",
                        "experience_type": "spot",
                        "trip_id": "trip_1",
                        "photos": [{"asset_id": "asset_1"}],
                        "pagination": {"limit": 20, "offset": 0, "count": 1},
                        "source": "photo_skill",
                    },
                },
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_experience_detail(
            "item_1", limit=100, offset=-1
        )

        self.assertEqual(response.experience_id, "item_1")
        self.assertEqual(response.timeline_item_id, "item_1")
        self.assertEqual(response.spot["experience_id"], "item_1")
        self.assertEqual(response.photos[0]["asset_id"], "asset_1")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "get_experience",
                    "params": {"experience_id": "item_1"},
                    "confirmed": False,
                    "role": "guest",
                },
                {
                    "tool_id": "get_experience_photos",
                    "params": {"experience_id": "item_1", "limit": 20, "offset": 0},
                    "confirmed": False,
                    "role": "admin",
                },
            ],
        )

    async def test_photo_api_executes_experience_photos_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "timeline_item_id": "item_1",
                        "experience_type": "event",
                        "trip_id": "trip_1",
                        "photos": [{"asset_id": "asset_1"}],
                        "pagination": {"limit": 20, "offset": 0, "count": 1},
                        "source": "photo_skill",
                    },
                }
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_experience_photos(
            "item_1", limit=100, offset=-1
        )

        self.assertEqual(response.experience_id, "item_1")
        self.assertEqual(response.experience_type, "event")
        self.assertEqual(response.timeline_item_id, "item_1")
        self.assertEqual(response.trip_id, "trip_1")
        self.assertEqual(response.photos[0]["asset_id"], "asset_1")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "get_experience_photos",
                    "params": {"experience_id": "item_1", "limit": 20, "offset": 0},
                    "confirmed": False,
                    "role": "admin",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
