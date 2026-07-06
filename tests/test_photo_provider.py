import inspect
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from backend.agent_host import AgentHost, Principal, TurnInput
from backend.domain_provider import OperationContext
from backend.executors import ExecutorRegistry
from backend.photo_executor import PhotoExecutor, PhotoProvider
from backend.photo_repository import PhotoRepository
from backend.provider_registry import ProviderRegistry
from backend.runtime import RuntimeService
from tests.fake_llm_client import FakeLLMClient


class PhotoProviderTest(unittest.TestCase):
    def test_recent_photo_observation_facts_are_deterministically_aggregated(self) -> None:
        repository = Mock()
        repository.get_photos.return_value = [
            {
                "asset_id": "asset-3",
                "taken_at": "2026-07-05T18:00:00+09:00",
                "has_location": True,
                "has_faces": True,
                "camera_make": "Apple",
                "camera_model": "iPhone 15",
                "timezone": "Asia/Tokyo",
            },
            {
                "asset_id": "asset-1",
                "taken_at": "2026-07-04T08:00:00+09:00",
                "has_location": False,
                "has_faces": True,
                "camera_make": "Apple",
                "camera_model": "iPhone 14",
                "timezone": "Asia/Tokyo",
            },
            {
                "asset_id": "asset-2",
                "taken_at": "2026-07-05T09:00:00+09:00",
                "has_location": True,
                "has_faces": False,
                "camera_make": "Apple",
                "camera_model": "iPhone 15",
                "timezone": "Asia/Tokyo",
            },
        ]
        provider = PhotoProvider(
            repository=repository,
            clock=lambda: datetime(2026, 7, 6, tzinfo=timezone.utc),
        )

        operation = OperationContext(
            operation_id="get_recent_photos",
            skill_id="photo",
            mode="read",
            risk_level="low",
        )
        result = provider.execute(operation, {})
        facts = provider.observation_details(operation, result)["facts"]

        self.assertEqual(
            facts["date_bucket_counts"], {"2026-07-04": 1, "2026-07-05": 2}
        )
        self.assertEqual(facts["day_count"], 2)
        self.assertEqual(facts["has_location_count"], 2)
        self.assertEqual(facts["has_faces_count"], 2)
        self.assertEqual(facts["camera_make_counts"], {"Apple": 3})
        self.assertEqual(
            facts["camera_model_counts"], {"iPhone 14": 1, "iPhone 15": 2}
        )
        self.assertEqual(facts["timezone"], "Asia/Tokyo")
        self.assertEqual(facts["oldest_photo_at"], "2026-07-04T08:00:00+09:00")
        self.assertEqual(facts["newest_photo_at"], "2026-07-05T18:00:00+09:00")
        self.assertFalse(
            {"message", "summary", "recommendation", "next_action"} & facts.keys()
        )

    def test_repository_exposes_only_available_camera_metadata(self) -> None:
        adapter = Mock()
        adapter.search_photos.return_value = [
            {
                "id": "asset-1",
                "fileCreatedAt": "2026-07-05T10:00:00+09:00",
                "exifInfo": {
                    "make": " Apple ",
                    "model": "iPhone 15",
                    "timeZone": "Asia/Tokyo",
                },
            }
        ]

        photo = PhotoRepository(adapter=adapter).get_photos(
            "2026-07-01T00:00:00+09:00", "2026-07-06T00:00:00+09:00", 20
        )[0]

        self.assertEqual(photo["camera_make"], "Apple")
        self.assertEqual(photo["camera_model"], "iPhone 15")
        self.assertEqual(photo["timezone"], "Asia/Tokyo")

    def test_operation_catalog_exposes_recent_photo_metadata_read(self) -> None:
        runtime = RuntimeService()
        photo = next(
            item
            for item in runtime.get_operation_catalog()["providers"]
            if item["provider_id"] == "photo"
        )
        operation = next(
            item
            for item in photo["operations"]
            if item["operation_id"] == "get_recent_photos"
        )

        self.assertEqual(operation["mode"], "read")
        self.assertEqual(operation["availability"], "implemented")
        self.assertFalse(operation["confirmation_required"])
        self.assertIn("does not display photos", operation["description"])

    def test_runtime_executes_recent_photo_metadata(self) -> None:
        repository = Mock()
        repository.get_photos.return_value = [
            {
                "asset_id": "asset-1",
                "taken_at": "2026-07-05T10:00:00+00:00",
                "has_location": True,
                "has_faces": False,
            }
        ]
        provider = PhotoProvider(
            repository=repository,
            clock=lambda: datetime(2026, 7, 6, tzinfo=timezone.utc),
        )
        registry = ProviderRegistry()
        registry.register(provider)
        executors = ExecutorRegistry()
        executors.register_skill("photo", PhotoExecutor(provider=provider))
        runtime = RuntimeService(
            provider_registry=registry, executor_registry=executors
        )

        response = runtime.execute_provider_operation(
            "photo", "get_recent_photos", {}, role="family"
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["execution_mode"], "immich_photo_metadata_read")
        self.assertEqual(response["result"]["photo_count"], 1)
        self.assertEqual(response["result"]["sample_photo_ids"], ["asset-1"])
        self.assertTrue(response["result"]["has_location"])
        self.assertEqual(response["result"]["connection_status"], "available")

    def test_unconfigured_immich_returns_safe_unavailable_facts(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            runtime = RuntimeService()
            response = runtime.execute_provider_operation(
                "photo", "get_recent_photos", {}, role="guest"
            )

        self.assertTrue(response["success"])
        result = response["result"]
        self.assertEqual(result["photo_count"], 0)
        self.assertEqual(result["source"], "unavailable")
        self.assertEqual(result["connection_status"], "unavailable")
        self.assertEqual(result["sample_photo_ids"], [])
        self.assertEqual(result["date_bucket_counts"], {})
        self.assertEqual(result["day_count"], 0)
        self.assertEqual(result["has_location_count"], 0)
        self.assertEqual(result["has_faces_count"], 0)
        self.assertEqual(result["camera_make_counts"], {})
        self.assertEqual(result["camera_model_counts"], {})
        self.assertTrue(result["limitations"])

    def test_observation_contains_photo_facts_and_preserves_raw_result(self) -> None:
        llm = FakeLLMClient(
            [
                {
                    "contract_version": "1",
                    "action": "call_operation",
                    "provider_id": "photo",
                    "operation_id": "get_recent_photos",
                    "arguments": {},
                    "conversation_update": {
                        "transition": "continue_unresolved_intent"
                    },
                },
                {
                    "contract_version": "1",
                    "action": "answer",
                    "message": "Immichは未設定です。",
                    "conversation_update": {"transition": "start_request"},
                },
            ]
        )
        with patch.dict(os.environ, {}, clear=True):
            turn = AgentHost(llm, RuntimeService()).run_turn(
                TurnInput(
                    session_id="photo-observation",
                    channel="chat",
                    normalized_input={"text": "最近の写真ある？"},
                    principal=Principal(role="family"),
                )
            )

        observation = turn.observations[0]
        self.assertEqual(observation.facts["photo_count"], 0)
        self.assertEqual(observation.facts["source"], "unavailable")
        self.assertEqual(observation.facts["connection_status"], "unavailable")
        self.assertEqual(observation.raw_result["result"]["sample_photo_ids"], [])
        self.assertTrue(observation.limitations)

    def test_no_photo_router_planner_or_python_answer_was_added(self) -> None:
        source = inspect.getsource(PhotoProvider)

        self.assertNotIn('if "写真"', source)
        self.assertNotIn("user_text", source)
        self.assertNotIn("Router", source)
        self.assertNotIn("Planner", source)
        self.assertNotIn("fallback", source.lower())


if __name__ == "__main__":
    unittest.main()
