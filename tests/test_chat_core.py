import json
import unittest

from pydantic import ValidationError

from backend.chat_core import (
    ChatResponseV1,
    ComposeRequest,
    ComposeResult,
    ContentBlock,
    ConversationState,
    ConversationTurn,
    ConversationWorkingContext,
    EntityCandidate,
    EntityRef,
    SuggestedAction,
    legacy_chat_response_to_v1,
)
from backend.travel_response_composer import TravelResponseComposer
from backend.travel_chat_adapter import (
    CLIENT_CONTEXT_SOURCE,
    RUNTIME_SOURCE,
    compose_travel_chat_response_v1,
    conversation_state_from_legacy_context,
    conversation_state_from_runtime_trip,
    legacy_context_from_conversation_state,
    travel_content_blocks,
)


class ChatCoreTest(unittest.TestCase):
    def test_conversation_working_context_is_bounded_and_separate_from_state(self) -> None:
        working_context = ConversationWorkingContext(
            turns=[
                ConversationTurn(role="user", content="神戸で何した？"),
                ConversationTurn(role="assistant", content="博物館へ行きました。"),
            ]
        )

        self.assertEqual(working_context.turns[0].role, "user")
        self.assertFalse(hasattr(ConversationState(), "turns"))
        with self.assertRaises(ValidationError):
            ConversationWorkingContext(
                turns=[
                    ConversationTurn(role="user", content=str(index))
                    for index in range(6)
                ]
            )

    def test_response_composer_protocol_models_carry_legacy_and_v1_outputs(self) -> None:
        request = ComposeRequest(outcome="not_found", diagnostics={"source": "test"})

        composed = TravelResponseComposer().compose(request)

        self.assertIsInstance(composed, ComposeResult)
        self.assertEqual(composed.response["action"], "needs_context")
        self.assertEqual(composed.response_v1.outcome, "needs_context")

    def test_foundation_types_validate_and_serialize(self) -> None:
        entity = EntityRef(
            skill_id="travel",
            entity_type="trip",
            entity_id="trip-fukuoka",
            label="福岡旅行",
            source="test",
        )
        candidate = EntityCandidate(entity=entity, score=0.9, matched_by="title")
        state = ConversationState(
            active_skill="travel",
            selected_entities=[entity],
            skill_slots={"travel": {"day": 2}},
        )
        response = ChatResponseV1(
            outcome="tool_result",
            message="取得しました。",
            content_blocks=[ContentBlock(type="travel_trip", data={"id": "trip-fukuoka"})],
            suggested_actions=[
                SuggestedAction(type="navigate", payload={"target": "#travel"})
            ],
            conversation_state=state,
        )

        self.assertEqual(candidate.entity.entity_id, "trip-fukuoka")
        self.assertEqual(response.version, "1")
        self.assertEqual(response.model_dump()["conversation_state"]["active_skill"], "travel")

    def test_candidate_score_is_bounded(self) -> None:
        entity = EntityRef(
            skill_id="travel",
            entity_type="trip",
            entity_id="trip-1",
            label="旅行",
            source="test",
        )
        with self.assertRaises(ValidationError):
            EntityCandidate(entity=entity, score=1.1, matched_by="title")

    def test_legacy_response_converts_without_changing_public_fields(self) -> None:
        legacy = {
            "action": "tool_result",
            "tool_id": "get_trip",
            "reply": "福岡旅行を開きます。",
            "result": {"trip": {"id": "trip-fukuoka"}},
            "navigation": {
                "target": "#travel?trip_id=trip-fukuoka",
                "label": "Travelで開く",
            },
            "debug": {"timings_ms": {"total": 1.0}},
        }

        converted = legacy_chat_response_to_v1(legacy)

        self.assertEqual(converted.outcome, legacy["action"])
        self.assertEqual(converted.message, legacy["reply"])
        self.assertEqual(converted.content_blocks[0].type, "tool_result")
        self.assertEqual(converted.suggested_actions[0].type, "navigate")
        self.assertEqual(converted.diagnostics, legacy["debug"])
        self.assertNotIn("version", legacy)

    def test_response_conversion_redacts_secrets(self) -> None:
        secret = "sk-chat-core-secret-value"
        converted = legacy_chat_response_to_v1(
            {
                "action": "tool_result",
                "reply": f"Bearer {secret}",
                "result": {"token": secret},
            }
        )

        serialized = json.dumps(converted.model_dump(mode="json"), ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("Bearer", serialized)

    def test_travel_composer_redacts_blocks_and_state(self) -> None:
        secret = "sk-travel-composer-secret-value"
        state = conversation_state_from_legacy_context(
            {
                "selected_trip_id": "trip-1",
                "selected_trip_title": f"Bearer {secret}",
            }
        )
        converted = compose_travel_chat_response_v1(
            {
                "action": "tool_result",
                "tool_id": "get_trip",
                "reply": "取得しました。",
                "result": {"trip": {"id": "trip-1", "memo": secret}},
            },
            conversation_state=state,
        )

        serialized = json.dumps(converted.model_dump(mode="json"), ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("Bearer", serialized)

    def test_legacy_context_becomes_unverified_trip_entity(self) -> None:
        state = conversation_state_from_legacy_context(
            {
                "selected_trip_id": " trip-fukuoka ",
                "selected_trip_title": " 福岡旅行 ",
                "role": "admin",
            }
        )

        entity = state.selected_entities[0]
        self.assertEqual(entity.entity_id, "trip-fukuoka")
        self.assertEqual(entity.label, "福岡旅行")
        self.assertEqual(entity.source, CLIENT_CONTEXT_SOURCE)
        self.assertIsNone(entity.verified_at)
        self.assertEqual(
            legacy_context_from_conversation_state(state),
            {
                "selected_trip_id": "trip-fukuoka",
                "selected_trip_title": "福岡旅行",
            },
        )

    def test_runtime_trip_becomes_verified_entity(self) -> None:
        state = conversation_state_from_runtime_trip(
            {"id": "trip-fukuoka", "title": "福岡旅行"}
        )

        entity = state.selected_entities[0]
        self.assertEqual(entity.source, RUNTIME_SOURCE)
        self.assertIsNotNone(entity.verified_at)

    def test_invalid_or_oversized_context_is_discarded(self) -> None:
        state = conversation_state_from_legacy_context(
            {"selected_trip_id": "x" * 257, "selected_trip_title": "旅行"}
        )

        self.assertEqual(state.selected_entities, [])
        self.assertEqual(legacy_context_from_conversation_state(state), {})

    def test_travel_content_and_response_composer_use_travel_blocks(self) -> None:
        legacy = {
            "action": "tool_result",
            "tool_id": "get_trips",
            "reply": "旅行一覧を取得しました。",
            "result": {"trips": [{"id": "trip-1"}]},
        }

        blocks = travel_content_blocks(legacy)
        converted = compose_travel_chat_response_v1(legacy)

        self.assertEqual(blocks[0].type, "travel_trip_list")
        self.assertEqual(converted.content_blocks, blocks)


if __name__ == "__main__":
    unittest.main()
