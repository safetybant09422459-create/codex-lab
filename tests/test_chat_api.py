import unittest
from unittest.mock import Mock, patch

import httpx

from backend import main, openai_adapter
from backend.agent_host import AgentHost
from tests.fake_llm_client import FakeLLMClient


def answer_action(message="こんにちは。"):
    return {
        "contract_version": "1",
        "action": "answer",
        "message": message,
        "conversation_update": {"transition": "start_request"},
    }


def call_action():
    return {
        "contract_version": "1",
        "action": "call_operation",
        "provider_id": "travel",
        "operation_id": "get_trips",
        "arguments": {},
        "conversation_update": {"transition": "continue_unresolved_intent"},
    }


class ChatApiTest(unittest.IsolatedAsyncioTestCase):
    async def post_chat(self, payload):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/api/chat", json=payload)

    async def test_chat_uses_agent_host_without_runtime_for_answer(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [],
        }
        host = AgentHost(FakeLLMClient(answer_action()), runtime)
        with patch.object(main, "agent_host", host):
            response = await self.post_chat({"message": "こんにちは", "debug": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "answer")
        self.assertEqual(response.json()["reply"], "こんにちは。")
        self.assertEqual(response.json()["debug"]["route"], "agent_host")
        self.assertNotIn("tool_id", response.json())
        self.assertNotIn("result", response.json())
        runtime.execute_provider_operation.assert_not_called()

    async def test_chat_call_operation_runs_runtime_then_returns_answer(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [
                {
                    "provider_id": "travel",
                    "operations": [
                        {
                            "operation_id": "get_trips",
                            "availability": "implemented",
                        }
                    ],
                }
            ],
        }
        runtime.execute_provider_operation.return_value = {
            "success": True,
            "tool_id": "get_trips",
            "result": {"trips": [{"id": "trip-1"}]},
        }
        llm = FakeLLMClient([call_action(), answer_action("旅行は1件あります。")])
        with patch.object(main, "agent_host", AgentHost(llm, runtime)):
            response = await self.post_chat({"message": "旅行一覧見せて"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "旅行は1件あります。")
        self.assertEqual(response.json()["tool_id"], "get_trips")
        self.assertEqual(response.json()["result"]["trips"][0]["id"], "trip-1")
        runtime.execute_provider_operation.assert_called_once_with(
            "travel", "get_trips", {}, confirmed=False, role="family"
        )
        self.assertEqual(llm.payloads[0].principal.role, "family")
        self.assertEqual(llm.payloads[0].principal.subject_id, "local-web-family")
        self.assertEqual(len(llm.payloads), 2)

    async def test_web_chat_family_entities_reach_next_turn_context(self) -> None:
        runtime = main.runtime_service
        llm = FakeLLMClient(
            [call_action(), answer_action("旅行一覧です。"), answer_action("開きます。")]
        )
        with patch.object(main, "agent_host", AgentHost(llm, runtime)):
            first = await self.post_chat(
                {"message": "旅行一覧見せて", "session_id": "family-context"}
            )
            second = await self.post_chat(
                {"message": "福岡旅行を開いて", "session_id": "family-context"}
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        entities = llm.payloads[2].conversation_state["active_entities"]
        self.assertTrue(entities)
        self.assertTrue(all(item["visibility"] == "family" for item in entities))
        self.assertTrue(all(item["id"] for item in entities))

    async def test_missing_openai_api_key_returns_safe_configuration_error(self) -> None:
        host = AgentHost(openai_adapter.OpenAIModelProviderAdapter(), Mock())
        host.runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [],
        }
        with (
            patch.object(main, "agent_host", host),
            patch.object(openai_adapter, "OPENAI_API_KEY", ""),
        ):
            response = await self.post_chat({"message": "こんにちは"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY is not configured", response.json()["detail"])

    async def test_history_is_bounded(self) -> None:
        response = await self.post_chat(
            {
                "message": "続けて",
                "conversation_history": [
                    {"role": "user", "content": str(index)} for index in range(6)
                ],
            }
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
