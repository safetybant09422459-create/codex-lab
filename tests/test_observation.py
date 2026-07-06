import inspect
import unittest
from datetime import datetime, timezone

from backend.agent_host import AgentHost, Principal, TurnInput
from backend.observation import ObservationEnvelopeBuilder
from backend.runtime import RuntimeService
from tests.fake_llm_client import FakeLLMClient


def call_action(provider_id: str, operation_id: str) -> dict:
    return {
        "contract_version": "1",
        "action": "call_operation",
        "provider_id": provider_id,
        "operation_id": operation_id,
        "arguments": {},
        "conversation_update": {"transition": "continue_unresolved_intent"},
    }


def answer_action() -> dict:
    return {
        "contract_version": "1",
        "action": "answer",
        "message": "確認しました。",
        "conversation_update": {"transition": "start_request"},
    }


class ObservationEnvelopeTest(unittest.TestCase):
    def test_envelope_preserves_raw_result_and_common_metadata(self) -> None:
        raw = {
            "success": True,
            "execution_mode": "local_read",
            "result": {"source": "repository", "items": [1]},
        }
        builder = ObservationEnvelopeBuilder(
            clock=lambda: datetime(2026, 7, 6, 1, 2, 3, tzinfo=timezone.utc)
        )

        envelope = builder.build(
            provider_id="example",
            operation_id="list_items",
            raw_result=raw,
            details={
                "facts": {"has_more": False},
                "counts": {"item_count": 1},
                "limitations": ["local only"],
                "visibility": "family",
                "related_capabilities": ["review_items"],
            },
        )

        self.assertEqual(envelope.raw_result, raw)
        self.assertIsNot(envelope.raw_result, raw)
        self.assertEqual(envelope.status, "success")
        self.assertEqual(envelope.facts, {"has_more": False})
        self.assertEqual(envelope.counts, {"item_count": 1})
        self.assertEqual(envelope.limitations, ["local only"])
        self.assertEqual(envelope.visibility, "family")
        self.assertEqual(envelope.freshness, "observed_at_execution")
        self.assertEqual(envelope.observed_at, "2026-07-06T01:02:03+00:00")
        self.assertEqual(envelope.provenance["source"], "repository")

    def test_get_trips_adds_only_deterministic_provider_facts(self) -> None:
        runtime = RuntimeService()
        raw = runtime.execute_provider_operation(
            "travel", "get_trips", {}, role="guest"
        )
        details = runtime.get_observation_details("travel", "get_trips", raw)

        self.assertEqual(details["facts"]["trip_count"], len(raw["result"]["trips"]))
        self.assertEqual(
            details["facts"]["titles"],
            [trip["title"] for trip in raw["result"]["trips"]],
        )
        self.assertIn("date_range", details["facts"])
        self.assertFalse(details["facts"]["has_more"])
        self.assertNotIn("next_action", details)

    def test_jarvis_capability_observation_has_deterministic_counts(self) -> None:
        runtime = RuntimeService()
        raw = runtime.execute_provider_operation(
            "jarvis", "get_capabilities", {}, role="guest"
        )
        details = runtime.get_observation_details(
            "jarvis", "get_capabilities", raw
        )

        self.assertEqual(
            details["facts"]["provider_count"],
            len(raw["result"]["available_providers"]),
        )
        self.assertGreater(details["facts"]["capability_count"], 0)
        self.assertGreater(details["facts"]["operation_count"], 0)

    def test_envelope_is_passed_to_llm_and_context_builder_state(self) -> None:
        llm = FakeLLMClient(
            [
                call_action("travel", "get_trips"),
                answer_action(),
                answer_action(),
            ]
        )
        host = AgentHost(llm, RuntimeService())
        first = host.run_turn(
            TurnInput(
                session_id="observation-context",
                channel="chat",
                normalized_input={"text": "旅行一覧"},
                principal=Principal(role="family"),
            )
        )
        host.run_turn(
            TurnInput(
                session_id="observation-context",
                channel="chat",
                normalized_input={"text": "続き"},
                principal=Principal(role="family"),
            )
        )

        self.assertEqual(llm.payloads[1].prior_observations, first.observations)
        stored = llm.payloads[2].conversation_state["last_observations"][0]
        self.assertEqual(stored["provider_id"], "travel")
        self.assertIn("raw_result", stored)
        self.assertIn("trip_count", stored["facts"])

    def test_observation_code_has_no_user_intent_or_action_selection_input(self) -> None:
        source = inspect.getsource(ObservationEnvelopeBuilder)
        signature = inspect.signature(RuntimeService.get_observation_details)

        self.assertEqual(
            list(signature.parameters),
            ["self", "provider_id", "operation_id", "result"],
        )
        self.assertNotIn("user_text", source)
        self.assertNotIn("next_action", source)
        self.assertNotIn("clarification", source)
        self.assertNotIn("keyword", source)


if __name__ == "__main__":
    unittest.main()
