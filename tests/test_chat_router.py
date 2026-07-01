import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from backend.basic_chat import handle_basic_chat
from backend.chat_core import ConversationTurn
from backend.chat_router import handle_chat
from backend import chat_router
from backend.rag_core import RagDocument, RagSearchResult


class ChatRouterTest(unittest.TestCase):
    def test_activation_candidates_are_hints_and_do_not_execute_travel(self) -> None:
        captured = {}

        def route_generator(**kwargs):
            captured.update(kwargs)
            return json.dumps({"route": "basic", "confidence": "high"}), None

        activation = RagSearchResult(
            document=RagDocument(
                id="travel:experience:item-1",
                source_skill="travel",
                entity_type="experience",
                entity_id="item-1",
                text="福岡旅行 マリンワールド海の中道 水族館",
                metadata={"trip_id": "trip-1"},
                visibility="private",
                updated_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
            ),
            score=0.9,
            matched_terms=["福岡", "水族館"],
            reason="lexical terms",
        )

        with (
            patch.object(chat_router, "activation_search", return_value=[activation]),
            patch.object(chat_router, "handle_travel_chat") as travel,
        ):
            result = handle_chat(
                "福岡で水族館に行ったのいつ？",
                route_text_generator=route_generator,
                basic_text_generator=lambda **_: ("確認できません。", None),
                debug=True,
            )

        travel.assert_not_called()
        self.assertIn("unverified recall hints", captured["input_text"])
        self.assertTrue(result["debug"]["activation_candidates_present"])
        self.assertTrue(result["debug"]["activation_supplied_to_router"])
        self.assertNotIn("activation_used", result["debug"])
        self.assertNotIn("text", result["debug"]["activation_results"][0])

    def test_basic_chat_answers_without_calling_travel(self) -> None:
        route_generator = lambda **_: (  # noqa: E731
            json.dumps({"route": "basic", "confidence": "high"}),
            {"total": 1.0},
        )
        basic_generator = lambda **_: (  # noqa: E731
            "おはようございます。",
            {"total": 2.0},
        )

        with patch.object(chat_router, "handle_travel_chat") as travel:
            result = handle_chat(
                "おはよう",
                route_text_generator=route_generator,
                basic_text_generator=basic_generator,
            )

        self.assertEqual(
            result,
            {"action": "direct_answer", "reply": "おはようございます。"},
        )
        travel.assert_not_called()

    def test_casual_food_question_stays_in_basic_chat(self) -> None:
        route_generator = lambda **_: (  # noqa: E731
            json.dumps({"route": "basic", "confidence": "high"}),
            None,
        )
        basic_generator = lambda **_: ("味の好みはないですが、ラーメンの話はできます。", None)  # noqa: E731

        with patch.object(chat_router, "handle_travel_chat") as travel:
            result = handle_chat(
                "ラーメン好き？",
                route_text_generator=route_generator,
                basic_text_generator=basic_generator,
            )

        self.assertEqual(result["action"], "direct_answer")
        travel.assert_not_called()

    def test_validated_travel_route_delegates_to_existing_adapter(self) -> None:
        route_generator = lambda **_: (  # noqa: E731
            json.dumps({"route": "travel", "confidence": "high"}),
            None,
        )
        expected = {"action": "tool_result", "reply": "旅行一覧です。"}

        with patch.object(
            chat_router, "handle_travel_chat", return_value=expected
        ) as travel:
            result = handle_chat(
                "旅行一覧を見せて",
                route_text_generator=route_generator,
            )

        self.assertEqual(result, expected)
        travel.assert_called_once()

    def test_final_answer_generator_is_only_forwarded_to_travel(self) -> None:
        route_generator = lambda **_: (  # noqa: E731
            json.dumps({"route": "travel", "confidence": "high"}),
            None,
        )
        final_generator = lambda **_: ("旅行の記録です。", None)  # noqa: E731

        with patch.object(
            chat_router,
            "handle_travel_chat",
            return_value={"action": "tool_result", "reply": "旅行の記録です。"},
        ) as travel:
            handle_chat(
                "福岡旅行なにした？",
                route_text_generator=route_generator,
                final_answer_text_generator=final_generator,
            )

        self.assertIs(
            travel.call_args.kwargs["final_answer_text_generator"],
            final_generator,
        )

    def test_invalid_route_falls_back_to_basic_without_skill_execution(self) -> None:
        invalid_route = lambda **_: (  # noqa: E731
            '{"route":"calendar","confidence":"high"}',
            None,
        )
        basic_generator = lambda **_: (  # noqa: E731
            "通常会話として回答します。",
            None,
        )

        with patch.object(chat_router, "handle_travel_chat") as travel:
            result = handle_chat(
                "こんにちは",
                route_text_generator=invalid_route,
                basic_text_generator=basic_generator,
                debug=True,
            )

        self.assertEqual(result["action"], "direct_answer")
        self.assertTrue(result["debug"]["routing"]["fallback"])
        travel.assert_not_called()

    def test_basic_chat_receives_time_and_ephemeral_history(self) -> None:
        captured = {}

        def generator(**kwargs):
            captured.update(kwargs)
            return "Jarvisです。", None

        result = handle_basic_chat(
            "あなたは誰？",
            conversation_history=[
                ConversationTurn(role="user", content="さっきの話を覚えてる？")
            ],
            text_generator=generator,
            now=datetime(2026, 6, 29, 12, 34, tzinfo=timezone.utc),
        )

        self.assertEqual(result["reply"], "Jarvisです。")
        self.assertIn("2026-06-29T12:34:00+00:00", captured["input_text"])
        self.assertIn("さっきの話を覚えてる？", captured["input_text"])


if __name__ == "__main__":
    unittest.main()
