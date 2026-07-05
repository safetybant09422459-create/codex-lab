import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.agent_host import (
    AgentContractError,
    AgentHost,
    FakeLLMClient,
    TurnInput,
)
from backend.audit import AuditLogger
from backend.executors import ExecutorRegistry
from backend.provider_registry import ProviderRegistry
from backend.runtime import RuntimeService
from backend.travel_executor import TravelExecutor, TravelProvider


def answer_action() -> dict:
    return {
        "contract_version": "1",
        "action": "answer",
        "message": "了解しました。",
        "conversation_update": {"transition": "start_request"},
    }


def call_action(provider_id: str = "travel", operation_id: str = "get_trips") -> dict:
    return {
        "contract_version": "1",
        "action": "call_operation",
        "provider_id": provider_id,
        "operation_id": operation_id,
        "arguments": {},
        "conversation_update": {"transition": "continue_unresolved_intent"},
    }


class AgentHostTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock()
        self.repository.get_trips.return_value = [{"id": "trip-1"}]
        provider = TravelProvider(repository=self.repository)
        registry = ProviderRegistry()
        registry.register(provider)
        executors = ExecutorRegistry()
        executors.register_skill("travel", TravelExecutor(provider=provider))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runtime = RuntimeService(
            audit_logger=AuditLogger(Path(self.temp_dir.name) / "audit.log"),
            executor_registry=executors,
            provider_registry=registry,
        )
        self.turn_input = TurnInput(
            session_id="session-1",
            channel="chat",
            normalized_input={"text": "入力内容"},
        )

    def test_operation_catalog_is_included_in_llm_payload(self) -> None:
        llm = FakeLLMClient(answer_action())

        AgentHost(llm, self.runtime).run_turn(self.turn_input)

        catalog = llm.payloads[0].available_operations
        self.assertEqual(catalog["contract_version"], "1")
        self.assertEqual(catalog["providers"][0]["provider_id"], "travel")

    def test_fake_llm_answer_action_is_returned_without_runtime_call(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [],
        }
        result = AgentHost(FakeLLMClient(answer_action()), runtime).run_turn(
            self.turn_input
        )

        self.assertEqual(result.action.action, "answer")
        self.assertEqual(result.observations, [])
        runtime.execute_provider_operation.assert_not_called()

    def test_fake_llm_call_operation_runs_through_runtime(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [
                {
                    "provider_id": "calendar",
                    "operations": [{"operation_id": "list_events"}],
                }
            ],
        }
        runtime.execute_provider_operation.return_value = {
            "success": True,
            "result": {"events": []},
        }

        result = AgentHost(
            FakeLLMClient(call_action("calendar", "list_events")), runtime
        ).run_turn(self.turn_input)

        self.assertEqual(result.action.action, "call_operation")
        runtime.execute_provider_operation.assert_called_once_with(
            "calendar", "list_events", {}, confirmed=False, role="guest"
        )
        self.assertEqual(result.observations[0].result["result"], {"events": []})

    def test_real_runtime_provider_path_executes_provider_operation(self) -> None:
        result = AgentHost(FakeLLMClient(call_action()), self.runtime).run_turn(
            self.turn_input
        )

        self.assertTrue(result.observations[0].result["success"])
        self.repository.get_trips.assert_called_once_with()

    def test_invalid_action_is_rejected_before_runtime(self) -> None:
        invalid = answer_action()
        invalid["reasoning"] = "hidden thought must not be accepted"
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [],
        }

        with self.assertRaises(AgentContractError):
            AgentHost(FakeLLMClient(invalid), runtime).run_turn(self.turn_input)

        runtime.execute_provider_operation.assert_not_called()

    def test_host_is_channel_and_provider_neutral(self) -> None:
        runtime = Mock()
        runtime.get_operation_catalog.return_value = {
            "contract_version": "1",
            "providers": [
                {
                    "provider_id": "calendar",
                    "operations": [{"operation_id": "list_events"}],
                }
            ],
        }
        runtime.execute_provider_operation.return_value = {"success": True}
        voice_input = self.turn_input.model_copy(update={"channel": "voice"})

        AgentHost(
            FakeLLMClient(call_action("calendar", "list_events")), runtime
        ).run_turn(voice_input)

        runtime.execute_provider_operation.assert_called_once()


if __name__ == "__main__":
    unittest.main()
