import json
import unittest
from typing import Any
from unittest.mock import patch

from backend import chat_router
from backend.chat_orchestrator import handle_travel_chat
from backend.chat_router import handle_chat


class RecordingRuntime:
    """Deterministic Runtime boundary used by the conversation contract tests."""

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
        return self.responses[len(self.calls) - 1]


def route_json_generator(value: dict[str, Any]):
    return lambda **_: (json.dumps(value, ensure_ascii=False), None)


def planner_json_generator(value: dict[str, Any]):
    return lambda **_: json.dumps(value, ensure_ascii=False)


class ConversationQualityTest(unittest.TestCase):
    """Hard invariants for representative turns; reply wording is not fixed."""

    def test_cqt_01_greeting_uses_no_capability_or_tool(self) -> None:
        with patch.object(chat_router, "handle_travel_chat") as travel:
            result = handle_chat(
                "こんにちは",
                debug=True,
                route_text_generator=route_json_generator(
                    {"route": "basic", "confidence": "high"}
                ),
                basic_text_generator=lambda **_: ("こんにちは。", None),
            )

        self.assertEqual(result["action"], "direct_answer")
        self.assertEqual(result["debug"]["routing"]["route"], "basic")
        self.assertEqual(result["debug"]["route"], "basic")
        travel.assert_not_called()

    def test_cqt_05_travel_meals_are_runtime_and_repository_grounded(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = RecordingRuntime(
            [
                {
                    "success": True,
                    "result": {
                        "tool_id": "get_trips",
                        "trips": [trip],
                        "source": "local_travel_read",
                    },
                },
                {
                    "success": True,
                    "result": {
                        "tool_id": "get_trip_timeline",
                        "trip_id": "trip-fukuoka",
                        "items": [
                            {"display_title": "屋台ラーメン", "category": "food"}
                        ],
                        "source": "local_travel_read",
                    },
                },
            ]
        )
        plan = {
            "action": "tool_proposal",
            "goal": "summarize_meals",
            "answer_mode": "meals",
            "required_evidence": ["trip", "timeline"],
            "tool_id": "get_trips",
            "arguments": {},
            "entity_query": "福岡旅行",
            "confidence": "high",
            "reply": "福岡旅行の記録を確認します。",
        }
        captured: dict[str, Any] = {}

        def final_answer(**kwargs):
            captured.update(kwargs)
            return "記録では屋台ラーメンを食べています。", None

        routed = {"action": "needs_context", "reply": "travel boundary"}
        with patch.object(
            chat_router, "handle_travel_chat", return_value=routed
        ) as travel:
            routing_result = handle_chat(
                "福岡旅行で何食べた？",
                route_text_generator=route_json_generator(
                    {"route": "travel", "confidence": "high"}
                ),
            )

        self.assertEqual(routing_result, routed)
        travel.assert_called_once()

        # Exercise the selected Travel boundary with deterministic Agent and
        # Runtime inputs; reply wording remains free.
        result = handle_travel_chat(
            "福岡旅行で何食べた？",
            debug=True,
            text_generator=planner_json_generator(plan),
            final_answer_text_generator=final_answer,
            runtime=runtime,
        )

        self.assertEqual(result["action"], "tool_result")
        self.assertEqual(result["debug"]["route"], "travel")
        self.assertTrue(result["debug"]["evidence_used"])
        self.assertEqual(result["debug"]["final_answer_source"], "llm")
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip_timeline"],
        )
        self.assertTrue(all(call["confirmed"] is False for call in runtime.calls))
        self.assertIn('"source":"local_travel_read"', captured["input_text"])
        self.assertIn(
            '"provenance":{"boundary":"runtime","source":"local_travel_read"}',
            captured["input_text"],
        )
        self.assertIn('"answer_mode":"meals"', captured["input_text"])
        self.assertIn("屋台ラーメン", captured["input_text"])
        self.assertNotIn("明太子", captured["input_text"])

    def test_cqt_13_ambiguous_photo_request_clarifies_without_tool(self) -> None:
        runtime = RecordingRuntime([])
        plan = {
            "action": "needs_context",
            "goal": "show_photos",
            "answer_mode": "photos",
            "required_evidence": ["trip", "experience", "photo"],
            "reply": "どの旅行の写真か教えてください。",
        }

        result = handle_travel_chat(
            "旅行の写真見せて",
            debug=True,
            text_generator=planner_json_generator(plan),
            runtime=runtime,
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(result["debug"]["steps"], [])
        self.assertFalse(result["debug"]["evidence_used"])
        self.assertEqual(runtime.calls, [])

    def test_unknown_request_does_not_force_a_tool(self) -> None:
        with patch.object(chat_router, "handle_travel_chat") as travel:
            result = handle_chat(
                "未対応の装置を量子同期して",
                debug=True,
                route_text_generator=route_json_generator(
                    {"route": "basic", "confidence": "low"}
                ),
                basic_text_generator=lambda **_: (
                    "その操作に対応する機能はありません。",
                    None,
                ),
            )

        self.assertEqual(result["action"], "direct_answer")
        self.assertEqual(result["debug"]["routing"]["route"], "basic")
        travel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
