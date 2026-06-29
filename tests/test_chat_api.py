import json
import unittest
from typing import Any
from unittest.mock import patch

import httpx

from backend import basic_chat, chat_orchestrator, chat_router, main


class FakeRuntimeService:
    def __init__(self, response: dict[str, Any] | list[dict[str, Any]]) -> None:
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
        if isinstance(self.response, list):
            return self.response[len(self.calls) - 1]
        return self.response


class ChatApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.route_patcher = patch.object(
            chat_router,
            "generate_text_with_timings",
            return_value=(
                json.dumps({"route": "travel", "confidence": "high"}),
                None,
            ),
        )
        self.route_patcher.start()

    def tearDown(self) -> None:
        self.route_patcher.stop()

    async def post_chat(self, payload: dict[str, Any]) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/api/chat", json=payload)

    async def test_post_chat_returns_trips_and_uses_default_admin_role(self) -> None:
        runtime = FakeRuntimeService(
            response={
                "success": True,
                "result": {
                    "tool_id": "get_trips",
                    "trips": [{"id": "trip-1"}],
                },
            }
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
        }
        expected = {
            "action": "tool_result",
            "tool_id": "get_trips",
            "arguments": {},
            "reply": "旅行一覧を取得しました。",
            "result": {
                "tool_id": "get_trips",
                "trips": [{"id": "trip-1"}],
            },
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat({"message": "旅行一覧を見せて"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(response.json()["action"], "tool_result")
        self.assertEqual(response.json()["result"]["trips"], [{"id": "trip-1"}])
        self.assertNotIn("debug", response.json())
        self.assertEqual(
            runtime.calls,
            [
                {
                    "tool_id": "get_trips",
                    "params": {},
                    "confirmed": False,
                    "role": "admin",
                }
            ],
        )

    async def test_post_chat_returns_basic_answer_without_travel(self) -> None:
        with (
            patch.object(
                chat_router,
                "generate_text_with_timings",
                return_value=(
                    json.dumps({"route": "basic", "confidence": "high"}),
                    None,
                ),
            ),
            patch.object(
                basic_chat,
                "generate_text_with_timings",
                return_value=("おはようございます。", None),
            ),
            patch.object(chat_router, "handle_travel_chat") as travel,
        ):
            response = await self.post_chat({"message": "おはよう"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"action": "direct_answer", "reply": "おはようございます。"},
        )
        travel.assert_not_called()

    async def test_client_role_is_ignored_and_server_role_is_used(self) -> None:
        expected = {
            "action": "needs_context",
            "reply": "対象を指定してください。",
            "debug": {"timings_ms": {"total": 1.25}},
        }

        with patch.object(main, "handle_chat", return_value=expected) as handle:
            response = await self.post_chat(
                {
                    "message": "旅行を見せて",
                    "role": "family",
                    "debug": True,
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["debug"]["timings_ms"]["total"], 1.25)
        handle.assert_called_once_with(
            "旅行を見せて",
            role="admin",
            debug=True,
            context=None,
            conversation_history=[],
        )

    async def test_conversation_history_is_validated_and_forwarded(self) -> None:
        expected = {"action": "needs_context", "reply": "対象を指定してください。"}
        history = [
            {"role": "user", "content": "神戸で何した？"},
            {"role": "assistant", "content": "博物館へ行きました。"},
        ]

        with patch.object(main, "handle_chat", return_value=expected) as handle:
            response = await self.post_chat(
                {"message": "大阪で何食べた？", "conversation_history": history}
            )

        self.assertEqual(response.status_code, 200)
        forwarded = handle.call_args.kwargs["conversation_history"]
        self.assertEqual([turn.model_dump() for turn in forwarded], history)

    async def test_conversation_history_rejects_more_than_five_turns(self) -> None:
        response = await self.post_chat(
            {
                "message": "大阪で何食べた？",
                "conversation_history": [
                    {"role": "user", "content": str(index)} for index in range(6)
                ],
            }
        )

        self.assertEqual(response.status_code, 422)

    async def test_broad_query_returns_clarification_contract(self) -> None:
        trips = [
            {"id": "trip-old", "title": "以前の旅行", "start_date": "2025-01-01"},
            {"id": "trip-new", "title": "最近の旅行", "start_date": "2026-01-01"},
        ]
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": trips}}
        )
        proposal = {
            "action": "tool_proposal",
            "goal": "clarify",
            "answer_mode": "clarification",
            "required_evidence": [],
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "low",
            "reply": "どの旅行か確認します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat({"message": "旅行を開いて"})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["action"], "needs_context")
        self.assertEqual(payload["candidates"], trips)
        self.assertEqual(payload["clarification"]["status"], "candidates")
        self.assertEqual(
            payload["clarification"]["reason"], "query_too_broad"
        )
        self.assertEqual(
            payload["clarification"]["recommended_action"],
            "select_candidate",
        )

    async def test_named_trip_response_keeps_navigation_and_two_runtime_steps(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "福岡旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat(
                {"message": "福岡旅行を開いて", "role": "admin", "debug": True}
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["tool_id"], "get_trip")
        self.assertEqual(payload["result"]["trip"], trip)
        self.assertEqual(
            payload["navigation"]["target"],
            "#travel?trip_id=trip-fukuoka",
        )
        self.assertEqual(payload["navigation"]["trip_id"], "trip-fukuoka")
        self.assertEqual(
            payload["updated_context"],
            {
                "selected_trip_id": "trip-fukuoka",
                "selected_trip_title": "福岡旅行",
            },
        )
        self.assertEqual(
            [step["tool_id"] for step in payload["debug"]["steps"]],
            ["get_trips", "get_trip"],
        )
        self.assertEqual(len(runtime.calls), 2)

    async def test_context_follow_up_uses_selected_trip_and_returns_context(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行", "memo": "屋台"}
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trip": trip}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trip",
            "arguments": {"trip_id": "model-invented-id"},
            "confidence": "high",
            "reply": "旅行を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat(
                {
                    "message": "この旅行の詳細見せて",
                    "context": {
                        "selected_trip_id": "trip-fukuoka",
                        "selected_trip_title": "福岡旅行",
                    },
                }
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["tool_id"], "get_trip")
        self.assertEqual(payload["arguments"], {"trip_id": "trip-fukuoka"})
        self.assertEqual(payload["updated_context"]["selected_trip_id"], "trip-fukuoka")

    async def test_write_proposal_is_not_executed(self) -> None:
        runtime = FakeRuntimeService(response={"success": True, "result": {}})
        proposal = {
            "action": "tool_proposal",
            "tool_id": "update_experience",
            "arguments": {"experience_id": "experience-1", "memo": "更新"},
            "confidence": "high",
            "reply": "体験を更新します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat({"message": "メモを更新して"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["action"], "pending_write_not_implemented"
        )
        self.assertEqual(runtime.calls, [])

    async def test_runtime_result_secrets_are_redacted_from_response(self) -> None:
        secret = "sk-chat-api-secret-value"
        runtime = FakeRuntimeService(
            response={
                "success": True,
                "result": {
                    "tool_id": "get_trips",
                    "trips": [{"note": f"Bearer {secret}"}],
                },
            }
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            response = await self.post_chat({"message": "旅行一覧を見せて"})

        response_text = response.text
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(secret, response_text)
        self.assertNotIn("Bearer", response_text)
        self.assertNotIn("Traceback", response_text)


if __name__ == "__main__":
    unittest.main()
