import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

from backend import main
from backend.audit import AuditLogger
from backend.runtime import RuntimeService
from backend.models import TravelExperienceCreateRequest, TravelExperienceUpdateRequest
from backend.travel_executor import TravelExecutor
from backend.travel_repository import TravelRepository


class FakeTravelSource:
    def __init__(self, item: dict[str, Any] | None = None) -> None:
        self.item = item
        self.created_kwargs: dict[str, Any] | None = None
        self.updated_kwargs: dict[str, Any] | None = None

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

    def update_timeline_item(
        self, timeline_item_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        self.updated_kwargs = dict(kwargs)
        if self.item is None or self.item["id"] != timeline_item_id:
            return None
        self.item = {
            **self.item,
            **kwargs,
            "updated_at": "2026-06-23T11:00:00+09:00",
        }
        return dict(self.item)

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
        self.assertEqual(
            result["pagination"],
            {"limit": 10, "offset": 2, "count": 1, "has_more": False},
        )

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

    def test_update_experience_partial_update_preserves_unspecified_fields(self) -> None:
        source = FakeTravelSource(
            {
                "id": "item_1",
                "trip_id": "trip_1",
                "item_type": "spot",
                "display_title": "水族館",
                "place_name": "旧施設",
                "memo": "before",
                "status": "planned",
                "updated_at": "2026-06-23T10:00:00+09:00",
            }
        )
        repository = TravelRepository(source=source, photo_provider=FakePhotoProvider())

        experience = repository.update_experience(
            experience_id="item_1", place_name="新施設", status="done"
        )

        self.assertEqual(source.updated_kwargs, {"place_name": "新施設", "status": "done"})
        self.assertEqual(experience["place_name"], "新施設")
        self.assertEqual(experience["display_title"], "水族館")
        self.assertEqual(experience["memo"], "before")
        self.assertEqual(experience["updated_at"], "2026-06-23T11:00:00+09:00")

    def test_update_experience_can_update_only_memo(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "memo": "before",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        experience = repository.update_experience(
            experience_id="item_1", memo="楽しかった"
        )

        self.assertEqual(experience["memo"], "楽しかった")
        self.assertEqual(experience["display_title"], "水族館")

    def test_update_experience_can_update_only_display_title(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "memo": "before",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        experience = repository.update_experience(
            experience_id="item_1", display_title="新しい水族館"
        )

        self.assertEqual(experience["display_title"], "新しい水族館")
        self.assertEqual(experience["memo"], "before")

    def test_update_experience_can_update_experience_type(self) -> None:
        source = FakeTravelSource(
            {
                "id": "item_1",
                "trip_id": "trip_1",
                "item_type": "spot",
                "display_title": "水族館",
            }
        )
        repository = TravelRepository(source=source, photo_provider=FakePhotoProvider())

        experience = repository.update_experience(
            experience_id="item_1", experience_type="event"
        )

        self.assertEqual(source.updated_kwargs, {"item_type": "event"})
        self.assertEqual(experience["item_type"], "event")
        self.assertEqual(experience["experience_type"], "event")

    def test_archive_experience_sets_status_and_remains_readable(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "memo",
                    "display_title": "ひとこと",
                    "status": "planned",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        archived = repository.archive_experience(experience_id="item_1")
        fetched = repository.get_experience("item_1")

        self.assertEqual(archived["status"], "archived")
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched["status"], "archived")

    def test_get_trip_timeline_keeps_experience_detail_shape(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "memo",
                    "display_title": "ひとこと",
                    "status": "archived",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )

        timeline = repository.get_trip_timeline("trip_1")

        self.assertEqual(timeline[0]["experience_id"], "item_1")
        self.assertEqual(timeline[0]["timeline_item_id"], "item_1")
        self.assertEqual(timeline[0]["experience_type"], "memo")
        self.assertEqual(timeline[0]["status"], "archived")


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

    def test_executes_update_and_archive_experience_tools(self) -> None:
        repository = TravelRepository(
            source=FakeTravelSource(
                {
                    "id": "item_1",
                    "trip_id": "trip_1",
                    "item_type": "spot",
                    "display_title": "水族館",
                    "status": "planned",
                }
            ),
            photo_provider=FakePhotoProvider(),
        )
        executor = TravelExecutor(repository=repository)

        update_result = executor.execute(
            SimpleNamespace(id="update_experience"),
            {"experience_id": "item_1", "memo": "更新"},
        )
        archive_result = executor.execute(
            SimpleNamespace(id="archive_experience"),
            {"experience_id": "item_1"},
        )

        self.assertEqual(update_result["experience"]["memo"], "更新")
        self.assertEqual(archive_result["experience"]["status"], "archived")

    def test_runtime_requires_confirmation_and_admin_for_update_tools(self) -> None:
        with TemporaryDirectory() as temp_dir:
            runtime_service = RuntimeService(
                audit_logger=AuditLogger(Path(temp_dir) / "audit.log")
            )

            guest_result = runtime_service.execute_stub(
                "update_experience",
                {"experience_id": "item_1", "memo": "更新"},
                confirmed=True,
                role="guest",
            )
            admin_unconfirmed_result = runtime_service.execute_stub(
                "archive_experience",
                {"experience_id": "item_1"},
                confirmed=False,
                role="admin",
            )

        self.assertTrue(guest_result["permission_denied"])
        self.assertTrue(admin_unconfirmed_result["blocked"])
        self.assertTrue(admin_unconfirmed_result["confirmation_required"])


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
                        "pagination": {
                            "limit": 20,
                            "offset": 0,
                            "count": 1,
                            "has_more": False,
                        },
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
                        "pagination": {
                            "limit": 20,
                            "offset": 0,
                            "count": 1,
                            "has_more": False,
                        },
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
        self.assertEqual(response.limit, 20)
        self.assertEqual(response.offset, 0)
        self.assertEqual(response.count, 1)
        self.assertEqual(response.has_more, False)
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

    async def test_photo_api_accepts_experience_photos_offset_page(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "timeline_item_id": "item_1",
                        "experience_type": "event",
                        "trip_id": "trip_1",
                        "photos": [{"asset_id": "asset_21"}],
                        "pagination": {
                            "limit": 20,
                            "offset": 20,
                            "count": 1,
                            "has_more": False,
                        },
                        "source": "photo_skill",
                    },
                }
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_get_experience_photos(
            "item_1", limit=20, offset=20
        )

        self.assertEqual(response.photos[0]["asset_id"], "asset_21")
        self.assertEqual(response.limit, 20)
        self.assertEqual(response.offset, 20)
        self.assertEqual(response.count, 1)
        self.assertEqual(response.has_more, False)
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "get_experience_photos",
                    "params": {"experience_id": "item_1", "limit": 20, "offset": 20},
                    "confirmed": False,
                    "role": "admin",
                },
            ],
        )

    async def test_api_updates_experience_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "timeline_item_id": "item_1",
                        "experience_type": "event",
                        "experience": {
                            "id": "item_1",
                            "experience_id": "item_1",
                            "timeline_item_id": "item_1",
                            "experience_type": "event",
                            "item_type": "event",
                            "display_title": "ショー",
                        },
                        "source": "local_travel_write",
                    },
                }
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_update_experience(
            "item_1",
            TravelExperienceUpdateRequest(display_title="ショー"),
        )

        self.assertEqual(response.experience_id, "item_1")
        self.assertEqual(response.experience_type, "event")
        self.assertEqual(response.execution_mode, "local_travel_write")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "update_experience",
                    "params": {
                        "experience_id": "item_1",
                        "display_title": "ショー",
                    },
                    "confirmed": True,
                    "role": "admin",
                },
            ],
        )

    async def test_api_creates_experience_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_created",
                        "timeline_item_id": "item_created",
                        "experience_type": "memo",
                        "experience": {
                            "id": "item_created",
                            "experience_id": "item_created",
                            "timeline_item_id": "item_created",
                            "experience_type": "memo",
                            "item_type": "memo",
                            "trip_id": "trip_1",
                            "display_title": "ひとこと",
                            "memo": "楽しかった",
                            "status": "completed",
                        },
                        "source": "local_travel_write",
                    },
                }
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_create_experience(
            "trip_1",
            TravelExperienceCreateRequest(
                experience_type="memo",
                display_title="ひとこと",
                memo="楽しかった",
                status="completed",
            ),
        )

        self.assertEqual(response.experience_id, "item_created")
        self.assertEqual(response.experience_type, "memo")
        self.assertEqual(response.execution_mode, "local_travel_write")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "create_experience",
                    "params": {
                        "trip_id": "trip_1",
                        "experience_type": "memo",
                        "display_title": "ひとこと",
                        "memo": "楽しかった",
                        "status": "completed",
                    },
                    "confirmed": True,
                    "role": "admin",
                },
            ],
        )

    async def test_api_archives_experience_through_runtime(self) -> None:
        runtime_service = FakeRuntimeService(
            [
                {
                    "success": True,
                    "result": {
                        "experience_id": "item_1",
                        "timeline_item_id": "item_1",
                        "experience_type": "memo",
                        "experience": {
                            "id": "item_1",
                            "experience_id": "item_1",
                            "timeline_item_id": "item_1",
                            "experience_type": "memo",
                            "item_type": "memo",
                            "display_title": "ひとこと",
                            "status": "archived",
                        },
                        "source": "local_travel_write",
                    },
                }
            ]
        )
        main.runtime_service = runtime_service

        response = await main.travel_archive_experience("item_1")

        self.assertEqual(response.experience["status"], "archived")
        self.assertEqual(
            runtime_service.calls,
            [
                {
                    "tool_id": "archive_experience",
                    "params": {"experience_id": "item_1"},
                    "confirmed": True,
                    "role": "admin",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
