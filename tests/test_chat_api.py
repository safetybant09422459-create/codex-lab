import json
import unittest
from typing import Any
from unittest.mock import patch

import httpx

from backend import chat_orchestrator, main


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


class ChatApiTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_debug_true_returns_timing(self) -> None:
        expected = {
            "action": "needs_context",
            "reply": "対象を指定してください。",
            "debug": {"timings_ms": {"total": 1.25}},
        }

        with patch.object(main, "handle_travel_chat", return_value=expected) as handle:
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
            "旅行を見せて", role="family", debug=True
        )

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
