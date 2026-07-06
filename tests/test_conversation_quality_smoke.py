import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from backend.agent_host import AgentHost, Principal, TurnInput
from backend.audit import AuditLogger
from backend.executors import ExecutorRegistry
from backend.photo_executor import PhotoExecutor, PhotoProvider
from backend.provider_registry import ProviderRegistry
from backend.runtime import RuntimeService
from backend.travel_executor import TravelExecutor, TravelProvider
from tests.fake_llm_client import FakeLLMClient


FUKUOKA_TRIP_ID = "trip-fukuoka"


def answer_action(message: str = "確認しました。", active_entities=None) -> dict:
    return {
        "contract_version": "1",
        "action": "answer",
        "message": message,
        "conversation_update": {
            "transition": "continue_topic",
            "active_entities": active_entities,
        },
    }


def call_action(provider_id: str, operation_id: str, arguments=None) -> dict:
    return {
        "contract_version": "1",
        "action": "call_operation",
        "provider_id": provider_id,
        "operation_id": operation_id,
        "arguments": arguments or {},
        "conversation_update": {"transition": "continue_unresolved_intent"},
    }


class ConversationQualitySmokeTest(unittest.TestCase):
    """Python Brain guard: verify LLM inputs, not conversational quality."""

    def setUp(self) -> None:
        self.travel_repository = Mock()
        self.travel_repository.get_trips.return_value = [
            {
                "id": FUKUOKA_TRIP_ID,
                "title": "福岡旅行",
                "start_date": "2026-06-01",
                "end_date": "2026-06-03",
            }
        ]
        self.travel_repository.get_trip.return_value = {
            "id": FUKUOKA_TRIP_ID,
            "title": "福岡旅行",
        }
        self.photo_repository = Mock()
        self.photo_repository.get_photos.return_value = [
            {
                "asset_id": "asset-1",
                "taken_at": "2026-07-04T10:00:00+09:00",
                "has_location": False,
                "has_faces": True,
                "timezone": "Asia/Tokyo",
            },
            {
                "asset_id": "asset-2",
                "taken_at": "2026-07-05T09:00:00+09:00",
                "has_location": True,
                "has_faces": False,
                "timezone": "Asia/Tokyo",
            },
            {
                "asset_id": "asset-3",
                "taken_at": "2026-07-05T18:00:00+09:00",
                "has_location": True,
                "has_faces": True,
                "timezone": "Asia/Tokyo",
            },
        ]

        travel_provider = TravelProvider(repository=self.travel_repository)
        photo_provider = PhotoProvider(
            repository=self.photo_repository,
            clock=lambda: datetime(2026, 7, 6, tzinfo=timezone.utc),
        )
        providers = ProviderRegistry()
        providers.register(travel_provider)
        providers.register(photo_provider)
        executors = ExecutorRegistry()
        executors.register_skill("travel", TravelExecutor(provider=travel_provider))
        executors.register_skill("photo", PhotoExecutor(provider=photo_provider))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runtime = RuntimeService(
            audit_logger=AuditLogger(Path(self.temp_dir.name) / "audit.log"),
            executor_registry=executors,
            provider_registry=providers,
        )

    @staticmethod
    def turn(session_id: str, text: str) -> TurnInput:
        return TurnInput(
            session_id=session_id,
            channel="chat",
            normalized_input={"text": text},
            principal=Principal(role="family"),
        )

    def assert_context_materials(self, payload, provider_id: str) -> None:
        self.assertTrue(payload.conversation_context)
        self.assertIn(
            provider_id,
            {item["provider_id"] for item in payload.capability_context},
        )

    def test_travel_list_then_count_has_observation_without_another_call(self) -> None:
        llm = FakeLLMClient(
            [
                call_action("travel", "get_trips"),
                answer_action(),
                answer_action(),
            ]
        )
        host = AgentHost(llm, self.runtime)

        host.run_turn(self.turn("travel-count", "旅行一覧見せて"))
        host.run_turn(self.turn("travel-count", "それ何件？"))

        follow_up = llm.payloads[2]
        self.assert_context_materials(follow_up, "travel")
        observation = follow_up.conversation_state["last_observations"][0]
        self.assertEqual(observation["facts"]["trip_count"], 1)
        self.travel_repository.get_trips.assert_called_once_with()

    def test_travel_list_then_open_exposes_canonical_active_entity(self) -> None:
        llm = FakeLLMClient(
            [
                call_action("travel", "get_trips"),
                answer_action(),
                call_action("travel", "get_trip", {"trip_id": FUKUOKA_TRIP_ID}),
                answer_action(),
            ]
        )
        host = AgentHost(llm, self.runtime)

        host.run_turn(self.turn("travel-open", "旅行一覧見せて"))
        host.run_turn(self.turn("travel-open", "福岡旅行を開いて"))

        follow_up = llm.payloads[2]
        self.assert_context_materials(follow_up, "travel")
        entity = follow_up.conversation_state["active_entities"][0]
        self.assertEqual(entity["label"], "福岡旅行")
        self.assertEqual(entity["id"], FUKUOKA_TRIP_ID)
        self.travel_repository.get_trip.assert_called_once_with(FUKUOKA_TRIP_ID)

    def test_travel_open_then_follow_up_reuses_observation_without_rerun(self) -> None:
        llm = FakeLLMClient(
            [
                call_action("travel", "get_trip", {"trip_id": FUKUOKA_TRIP_ID}),
                answer_action(
                    active_entities=[
                        {
                            "entity_type": "trip",
                            "id": FUKUOKA_TRIP_ID,
                            "label": "福岡旅行",
                            "visibility": "family",
                        }
                    ]
                ),
                answer_action(),
            ]
        )
        host = AgentHost(llm, self.runtime)

        host.run_turn(self.turn("travel-detail", "福岡旅行を開いて"))
        host.run_turn(self.turn("travel-detail", "それについて教えて"))

        follow_up = llm.payloads[2]
        self.assert_context_materials(follow_up, "travel")
        observation = follow_up.conversation_state["last_observations"][0]
        self.assertEqual(observation["operation_id"], "get_trip")
        self.assertEqual(
            observation["raw_result"]["result"]["trip"]["id"], FUKUOKA_TRIP_ID
        )
        self.travel_repository.get_trip.assert_called_once_with(FUKUOKA_TRIP_ID)

    def test_recent_photos_then_date_question_exposes_observation_facts(self) -> None:
        follow_up = self._run_photo_follow_up("何日に多い？", "photo-dates")

        self.assert_context_materials(follow_up, "photo")
        facts = follow_up.conversation_state["last_observations"][0]["facts"]
        self.assertEqual(
            facts["date_bucket_counts"], {"2026-07-04": 1, "2026-07-05": 2}
        )
        self.photo_repository.get_photos.assert_called_once()

    def test_recent_photos_then_location_question_exposes_observation_facts(self) -> None:
        follow_up = self._run_photo_follow_up("位置情報は？", "photo-location")

        self.assert_context_materials(follow_up, "photo")
        facts = follow_up.conversation_state["last_observations"][0]["facts"]
        self.assertEqual(facts["has_location_count"], 2)
        self.photo_repository.get_photos.assert_called_once()

    def _run_photo_follow_up(self, question: str, session_id: str):
        llm = FakeLLMClient(
            [
                call_action("photo", "get_recent_photos"),
                answer_action(),
                answer_action(),
            ]
        )
        host = AgentHost(llm, self.runtime)
        host.run_turn(self.turn(session_id, "最近の写真ある？"))
        host.run_turn(self.turn(session_id, question))
        return llm.payloads[2]

    def test_small_talk_does_not_require_provider(self) -> None:
        for index, text in enumerate(("こんにちは", "元気？")):
            with self.subTest(text=text):
                llm = FakeLLMClient(answer_action())
                host = AgentHost(llm, self.runtime)

                result = host.run_turn(self.turn(f"small-talk-{index}", text))

                self.assertEqual(result.observations, [])
                self.assertFalse(
                    any(
                        event.event == "runtime_called"
                        for event in result.trace.events
                    )
                )
                self.assertIn(
                    "travel",
                    {
                        item["provider_id"]
                        for item in llm.payloads[0].capability_context
                    },
                )


if __name__ == "__main__":
    unittest.main()
