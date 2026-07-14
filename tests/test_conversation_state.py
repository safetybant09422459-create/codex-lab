import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import httpx

from backend import main
from backend.agent_host import AgentHost, TurnInput
from backend.conversation_state import (
    ConversationTurnState,
    InMemoryConversationStateStore,
)
from tests.fake_llm_client import FakeLLMClient


def answer_action(message: str, active_entities=None) -> dict:
    return {
        "contract_version": "1",
        "action": "answer",
        "message": message,
        "conversation_update": {
            "transition": "continue_topic",
            "active_entities": active_entities,
        },
    }


def call_action() -> dict:
    return {
        "contract_version": "1",
        "action": "call_operation",
        "provider_id": "travel",
        "operation_id": "get_trips",
        "arguments": {},
        "conversation_update": {"transition": "continue_unresolved_intent"},
    }


class ConversationStateStoreTest(unittest.TestCase):
    def test_max_turns_drops_oldest_turn(self) -> None:
        store = InMemoryConversationStateStore(max_turns=2)
        for index in range(3):
            store.append_turn(
                "session-1",
                ConversationTurnState(
                    user_input={"text": str(index)},
                    assistant_final_response=f"reply-{index}",
                    last_llm_action={"action": "answer"},
                ),
            )

        turns = store.get_turns("session-1")
        self.assertEqual([turn.user_input["text"] for turn in turns], ["1", "2"])

    def test_clear_session_removes_turns_and_started_at(self) -> None:
        store = InMemoryConversationStateStore()
        store.append_turn(
            "session-1",
            ConversationTurnState(
                user_input={"text": "private working context"},
                assistant_final_response="reply",
                last_llm_action={"action": "answer"},
            ),
        )

        store.clear_session("session-1")

        self.assertEqual(store.get_turns("session-1"), [])
        self.assertNotIn("session-1", store._session_started_at)

    def test_expired_session_is_removed_before_context_assembly(self) -> None:
        now = [datetime(2026, 7, 14, tzinfo=timezone.utc)]
        store = InMemoryConversationStateStore(
            session_ttl=timedelta(hours=1), clock=lambda: now[0]
        )
        store.append_turn(
            "expired",
            ConversationTurnState(
                user_input={"text": "temporary"},
                assistant_final_response="reply",
                last_llm_action={"action": "answer"},
            ),
        )

        now[0] += timedelta(hours=1)

        self.assertEqual(store.get_turns("expired"), [])
        self.assertNotIn("expired", store._session_started_at)

    def test_capacity_evicts_least_recently_used_session(self) -> None:
        now = [datetime(2026, 7, 14, tzinfo=timezone.utc)]
        store = InMemoryConversationStateStore(
            max_sessions=2, clock=lambda: now[0]
        )
        turn = ConversationTurnState(
            user_input={"text": "temporary"},
            assistant_final_response="reply",
            last_llm_action={"action": "answer"},
        )
        store.append_turn("keep", turn)
        now[0] += timedelta(seconds=1)
        store.append_turn("evict", turn)
        now[0] += timedelta(seconds=1)
        store.get_turns("keep")
        now[0] += timedelta(seconds=1)

        store.append_turn("new", turn)

        self.assertEqual(store.get_turns("evict"), [])
        self.assertEqual(len(store.get_turns("keep")), 1)
        self.assertEqual(len(store.get_turns("new")), 1)

    def test_state_limits_reject_invalid_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_sessions"):
            InMemoryConversationStateStore(max_sessions=0)
        with self.assertRaisesRegex(ValueError, "session_ttl"):
            InMemoryConversationStateStore(session_ttl=timedelta(0))

    def test_store_does_not_interpret_topics_or_entities(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [],
        }
        llm_entities = [{"opaque": "LLMが返した値"}]
        llm = FakeLLMClient(
            [answer_action("最初", llm_entities), answer_action("続きです")]
        )
        host = AgentHost(llm, runtime)

        host.run_turn(
            TurnInput(
                session_id="session-1",
                channel="chat",
                normalized_input={"text": "それの続き"},
            )
        )
        host.run_turn(
            TurnInput(
                session_id="session-1",
                channel="chat",
                normalized_input={"text": "別の話"},
            )
        )

        state = llm.payloads[1].conversation_state
        self.assertEqual(state["active_entities"], llm_entities)
        self.assertEqual(
            state["last_llm_action"]["conversation_update"]["transition"],
            "continue_topic",
        )


class ConversationStateApiTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def runtime() -> Mock:
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
            "result": {"trips": [{"id": "trip-1"}]},
        }
        return runtime

    async def post_chat(self, payload: dict) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/api/chat", json=payload)

    async def reset_chat(self, session_id: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                "/api/chat/session/reset", json={"session_id": session_id}
            )

    async def test_same_session_includes_previous_turn_in_payload(self) -> None:
        llm = FakeLLMClient(
            [answer_action("前の回答"), answer_action("次の回答")]
        )
        with patch.object(main, "agent_host", AgentHost(llm, self.runtime())):
            await self.post_chat({"message": "最初", "session_id": "same"})
            await self.post_chat({"message": "続き", "session_id": "same"})

        self.assertEqual(
            llm.payloads[1].conversation_context,
            [
                {
                    "user_input": {"text": "最初"},
                    "assistant_final_response": "前の回答",
                    "source": "server_turn",
                }
            ],
        )

    async def test_different_sessions_do_not_share_turns(self) -> None:
        llm = FakeLLMClient(
            [answer_action("A", [{"id": "session-a-entity"}]), answer_action("B")]
        )
        with patch.object(main, "agent_host", AgentHost(llm, self.runtime())):
            await self.post_chat({"message": "最初", "session_id": "session-a"})
            await self.post_chat({"message": "続き", "session_id": "session-b"})

        self.assertEqual(llm.payloads[1].conversation_context, [])
        self.assertEqual(llm.payloads[1].conversation_state["last_observations"], [])
        self.assertEqual(llm.payloads[1].conversation_state["active_entities"], [])

    async def test_client_history_is_fallback_hint_when_server_state_is_empty(self) -> None:
        llm = FakeLLMClient(answer_action("続きです"))
        with patch.object(main, "agent_host", AgentHost(llm, self.runtime())):
            response = await self.post_chat(
                {
                    "message": "続けて",
                    "session_id": "restored-tab",
                    "conversation_history": [
                        {"role": "user", "content": "前の質問"},
                        {"role": "assistant", "content": "前の回答"},
                    ],
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            llm.payloads[0].conversation_context,
            [
                {
                    "user_input": {"text": "前の質問"},
                    "assistant_final_response": "前の回答",
                    "source": "client_history_hint",
                }
            ],
        )
        self.assertIsNone(llm.payloads[0].conversation_state["last_llm_action"])

    async def test_server_state_takes_precedence_over_client_history_hint(self) -> None:
        llm = FakeLLMClient([answer_action("server"), answer_action("next")])
        with patch.object(main, "agent_host", AgentHost(llm, self.runtime())):
            await self.post_chat(
                {"message": "正本の会話", "session_id": "precedence"}
            )
            await self.post_chat(
                {
                    "message": "続き",
                    "session_id": "precedence",
                    "conversation_history": [
                        {"role": "user", "content": "偽の質問"},
                        {"role": "assistant", "content": "偽の回答"},
                    ],
                }
            )

        context = llm.payloads[1].conversation_context
        self.assertEqual(context[0]["user_input"]["text"], "正本の会話")
        self.assertEqual(context[0]["source"], "server_turn")

    async def test_reset_endpoint_removes_server_side_working_context(self) -> None:
        llm = FakeLLMClient(
            [answer_action("前の回答"), answer_action("新しい会話")]
        )
        host = AgentHost(llm, self.runtime())
        with patch.object(main, "agent_host", host):
            await self.post_chat({"message": "最初", "session_id": "clear-me"})
            reset = await self.reset_chat("clear-me")
            await self.post_chat({"message": "新しく開始", "session_id": "clear-me"})

        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json(), {"status": "cleared"})
        self.assertEqual(llm.payloads[1].conversation_context, [])
        self.assertEqual(llm.payloads[1].conversation_state["active_entities"], [])

    async def test_observation_is_in_next_turn_payload(self) -> None:
        llm = FakeLLMClient(
            [call_action(), answer_action("旅行があります"), answer_action("続きです")]
        )
        with patch.object(main, "agent_host", AgentHost(llm, self.runtime())):
            await self.post_chat({"message": "旅行一覧", "session_id": "observed"})
            await self.post_chat({"message": "それの続き", "session_id": "observed"})

        next_turn = llm.payloads[2]
        observations = next_turn.conversation_state["last_observations"]
        self.assertEqual(
            observations[0]["raw_result"]["result"]["trips"][0]["id"],
            "trip-1",
        )


if __name__ == "__main__":
    unittest.main()
