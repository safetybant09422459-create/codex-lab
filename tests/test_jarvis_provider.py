import inspect
import unittest

from backend.agent_host import AgentHost, TurnInput
from backend.jarvis_provider import JarvisProvider
from backend.runtime import RuntimeService
from tests.fake_llm_client import FakeLLMClient


class JarvisProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = RuntimeService()

    def _execute(self, operation_id: str) -> dict:
        response = self.runtime.execute_provider_operation(
            "jarvis", operation_id, {}, role="guest"
        )
        self.assertTrue(response["success"])
        self.assertEqual(response["execution_mode"], "local_jarvis_status_read")
        self.assertFalse(response["blocked"])
        self.assertFalse(response["confirmation_required"])
        return response["result"]

    def test_get_capabilities_executes_through_runtime(self) -> None:
        result = self._execute("get_capabilities")

        self.assertEqual(result["chat_status"], "active_single_agent_loop_v0")
        self.assertIn("jarvis", result["available_providers"])
        self.assertIn(
            "jarvis.get_capabilities", result["available_operations"]
        )

    def test_get_provider_status_executes_through_runtime(self) -> None:
        result = self._execute("get_provider_status")
        statuses = {
            item["provider_id"]: item["status"] for item in result["providers"]
        }

        self.assertEqual(statuses["jarvis"], "active")
        self.assertEqual(statuses["travel"], "active")
        self.assertEqual(statuses["photo"], "partial")
        self.assertEqual(statuses["calendar"], "planned")
        self.assertEqual(statuses["garden"], "planned")
        self.assertEqual(statuses["home"], "planned")

    def test_get_operation_catalog_executes_through_runtime(self) -> None:
        result = self._execute("get_operation_catalog")
        providers = {
            item["provider_id"]: item["operations"] for item in result["providers"]
        }

        self.assertIn("jarvis", providers)
        operation_ids = {item["operation_id"] for item in providers["jarvis"]}
        self.assertEqual(
            operation_ids,
            {
                "get_capabilities",
                "get_provider_status",
                "get_operation_catalog",
            },
        )

    def test_catalog_marks_jarvis_operations_read_only_and_low_risk(self) -> None:
        catalog = self.runtime.get_operation_catalog()
        jarvis = next(
            item for item in catalog["providers"] if item["provider_id"] == "jarvis"
        )

        self.assertEqual(len(jarvis["operations"]), 3)
        for operation in jarvis["operations"]:
            self.assertEqual(operation["mode"], "read")
            self.assertEqual(operation["risk_level"], "low")
            self.assertFalse(operation["confirmation_required"])
            self.assertEqual(operation["availability"], "implemented")

    def test_agent_host_returns_jarvis_observation_to_llm(self) -> None:
        llm = FakeLLMClient(
            [
                {
                    "contract_version": "1",
                    "action": "call_operation",
                    "provider_id": "jarvis",
                    "operation_id": "get_capabilities",
                    "arguments": {},
                    "conversation_update": {
                        "transition": "continue_unresolved_intent"
                    },
                },
                {
                    "contract_version": "1",
                    "action": "answer",
                    "message": "現在利用できる機能を確認しました。",
                    "conversation_update": {"transition": "start_request"},
                },
            ]
        )

        turn = AgentHost(llm, self.runtime).run_turn(
            TurnInput(
                session_id="jarvis-status-test",
                channel="web_chat",
                normalized_input={"text": "何ができる？"},
            )
        )

        self.assertEqual(turn.action.action, "answer")
        self.assertEqual(len(turn.observations), 1)
        self.assertEqual(
            turn.observations[0].result["result"]["source"], "operation_catalog"
        )
        self.assertEqual(len(llm.payloads), 2)
        self.assertEqual(len(llm.payloads[1].prior_observations), 1)

    def test_provider_has_no_user_text_or_answer_composer_boundary(self) -> None:
        execute_parameters = inspect.signature(JarvisProvider.execute).parameters
        source = inspect.getsource(JarvisProvider)

        self.assertEqual(
            list(execute_parameters), ["self", "operation", "arguments"]
        )
        self.assertNotIn("user_text", source)
        self.assertNotIn("compose_answer", source)


if __name__ == "__main__":
    unittest.main()
