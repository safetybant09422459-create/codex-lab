import inspect
import json
import tempfile
import unittest
from pathlib import Path

from backend.agent_host import AgentHost, TurnInput
from backend.jarvis_provider import JarvisProvider
from backend.provider_registry import ProviderRegistry
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
        capabilities = {
            item["provider_id"]: item["capabilities"]
            for item in result["capability_catalog"]["providers"]
        }
        self.assertEqual(
            capabilities["jarvis"][0]["description"],
            "Jarvisの状態や使える機能を確認できます",
        )
        self.assertIn("旅行を振り返れます", capabilities["travel"][0]["description"])
        self.assertEqual(
            capabilities["photo"][0]["description"], "写真機能は一部準備中です"
        )
        self.assertEqual(capabilities["travel"][0]["availability"], "available")
        self.assertEqual(capabilities["photo"][0]["availability"], "partial")

    def test_get_provider_status_executes_through_runtime(self) -> None:
        result = self._execute("get_provider_status")
        providers = {
            item["provider_id"]: item for item in result["providers"]
        }

        self.assertTrue(providers["jarvis"]["registered"])
        self.assertTrue(providers["travel"]["registered"])
        self.assertFalse(providers["photo"]["registered"])
        self.assertIn("capabilities", providers["calendar"])

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
        self.assertNotIn("capability_catalog", result)

    def test_missing_capability_metadata_uses_generic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skill_dir = skills_dir / "example"
            skill_dir.mkdir(parents=True)
            (skill_dir / "skill.json").write_text(
                json.dumps({"id": "example", "name": "Example", "status": "idea"}),
                encoding="utf-8",
            )
            registry = ProviderRegistry(skills_dir=skills_dir)

            entry = registry.capability_catalog()["providers"][0]

        self.assertEqual(entry["provider_id"], "example")
        self.assertEqual(
            entry["capabilities"],
            [
                {
                    "id": "description_unavailable",
                    "description": "User-facing capability descriptions are not declared.",
                }
            ],
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
        self.assertNotIn('provider_id == "travel"', source)
        self.assertNotIn('provider_id == "photo"', source)
        self.assertNotIn('"何ができる"', source)


if __name__ == "__main__":
    unittest.main()
