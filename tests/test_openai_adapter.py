import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import openai_adapter
from backend.agent_host import LLMInputPayload, Principal


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": "OK\n"})()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class OpenAIAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        openai_adapter._client = None

    def tearDown(self) -> None:
        openai_adapter._client = None

    @staticmethod
    def action_payload() -> LLMInputPayload:
        return LLMInputPayload(
            turn_id="turn-1",
            session_id="session-1",
            principal=Principal(role="guest"),
            channel="chat",
            normalized_input={"text": "旅行一覧を見せて"},
            conversation_context=[],
            conversation_state={},
            persona_context={},
            memory_context=[],
            activation_candidates=[],
            available_operations={"contract_version": "1", "providers": []},
            runtime_policy={"max_steps": 2},
            prior_observations=[],
        )

    @staticmethod
    def answer_action() -> dict[str, object]:
        return {
            "contract_version": "1",
            "action": "answer",
            "message": "了解しました。",
            "conversation_update": {
                "transition": "start_request",
                "current_topic": None,
                "previous_topic": None,
                "active_entities": None,
                "pending_question": None,
                "unresolved_intent": None,
            },
        }

    @classmethod
    def structured_answer(cls) -> str:
        return json.dumps({"llm_action": cls.answer_action()})

    def test_llm_client_request_contains_contract_payload_and_schema(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **kwargs: (
            client.responses.calls.append(kwargs)
            or SimpleNamespace(output_text=self.structured_answer())
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                self.action_payload()
            )

        request = client.responses.calls[0]
        sent_payload = json.loads(str(request["input"]))
        self.assertEqual(sent_payload["contract_version"], "1")
        self.assertEqual(sent_payload["normalized_input"]["text"], "旅行一覧を見せて")
        self.assertEqual(request["model"], "test-model")
        self.assertFalse(request["store"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        output_schema = request["text"]["format"]["schema"]
        self.assertEqual(output_schema["type"], "object")
        self.assertIn("llm_action", output_schema["properties"])
        self.assertNotIn("test-secret", repr(request))
        self.assertEqual(result["action"], "answer")

    def test_call_operation_action_is_returned_without_semantic_changes(self) -> None:
        client = FakeClient()
        action = {
            "contract_version": "1",
            "action": "call_operation",
            "provider_id": "travel",
            "operation_id": "get_trips",
            "arguments": {},
            "conversation_update": {
                "transition": "continue_unresolved_intent",
                "current_topic": None,
                "previous_topic": None,
                "active_entities": None,
                "pending_question": None,
                "unresolved_intent": None,
            },
        }
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text=json.dumps({"llm_action": action})
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                self.action_payload()
            )

        self.assertEqual(result, action)

    def test_provider_reasoning_item_is_not_returned_or_saved(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text=self.structured_answer(),
            output=[SimpleNamespace(type="reasoning", content="hidden thought")],
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                self.action_payload()
            )

        self.assertNotIn("reasoning", result)
        self.assertNotIn("hidden thought", repr(result))

    def test_invalid_structured_action_raises_validation_error(self) -> None:
        client = FakeClient()
        invalid = self.answer_action()
        invalid["reasoning"] = "must not enter the contract"
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text=json.dumps({"llm_action": invalid})
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            with self.assertRaises(openai_adapter.OpenAIResponseValidationError):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_llm_client_error_redacts_api_key(self) -> None:
        api_key = "sk-adapter-super-secret"
        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"Bearer {api_key}"),
            ),
        ):
            with self.assertRaises(openai_adapter.OpenAIRequestError) as context:
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

        self.assertNotIn(api_key, str(context.exception))

    def test_llm_client_without_api_key_fails_before_request(self) -> None:
        with patch.object(openai_adapter, "OPENAI_API_KEY", ""):
            with self.assertRaisesRegex(
                openai_adapter.OpenAIConfigurationError, "OPENAI_API_KEY"
            ):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_generate_text_reuses_client_within_process(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter, "_create_client", return_value=client
            ) as create_client,
        ):
            for _ in range(2):
                openai_adapter.generate_text(
                    instructions="Return JSON.",
                    input_text="旅行一覧を見せて",
                )

        create_client.assert_called_once_with()
        self.assertEqual(len(client.responses.calls), 2)

    def test_generate_text_keeps_server_request_unstored(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.generate_text(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(result, "OK")
        self.assertEqual(
            client.responses.calls,
            [
                {
                    "model": "test-model",
                    "instructions": "Return JSON.",
                    "input": "旅行一覧を見せて",
                    "store": False,
                    "max_output_tokens": 256,
                }
            ],
        )

    def test_generate_text_applies_configured_inference_settings(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5.4-mini"),
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "192"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", "none"),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", "low"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            openai_adapter.generate_text(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(
            client.responses.calls[0],
            {
                "model": "gpt-5.4-mini",
                "instructions": "Return JSON.",
                "input": "旅行一覧を見せて",
                "store": False,
                "reasoning": {"effort": "none"},
                "text": {"verbosity": "low"},
                "max_output_tokens": 192,
            },
        )

    def test_unset_optional_settings_preserve_api_defaults(self) -> None:
        with (
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
        ):
            settings = openai_adapter._inference_settings()

        self.assertEqual(settings, {"max_output_tokens": 256})

    def test_invalid_inference_setting_is_rejected_locally(self) -> None:
        with (
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", "fastest"),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
        ):
            with self.assertRaises(openai_adapter.OpenAIConfigurationError):
                openai_adapter._inference_settings()

    def test_generate_text_with_timings_returns_numeric_adapter_timings(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            text, timings = openai_adapter.generate_text_with_timings(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(text, "OK")
        self.assertEqual(
            set(timings),
            {"api_call", "response_text_extraction", "total"},
        )
        self.assertTrue(
            all(isinstance(value, (int, float)) for value in timings.values())
        )

    def test_generate_text_error_does_not_expose_api_key(self) -> None:
        api_key = "sk-test-generate-secret"

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"invalid Bearer {api_key}"),
            ),
        ):
            with self.assertRaises(openai_adapter.OpenAIRequestError) as context:
                openai_adapter.generate_text(
                    instructions="Return JSON.",
                    input_text="旅行一覧を見せて",
                )

        self.assertNotIn(api_key, str(context.exception))

    def test_check_openai_connection_uses_server_configuration(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(result, "OK")
        self.assertEqual(
            client.responses.calls,
            [
                {
                    "model": "test-model",
                    "input": "Reply with OK only.",
                    "store": False,
                }
            ],
        )

    def test_extracts_output_text_from_responses_api_items(self) -> None:
        response = SimpleNamespace(
            output_text="",
            output=[
                SimpleNamespace(type="reasoning", content=[]),
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", text="OK\n")],
                ),
            ],
        )
        client = FakeClient()
        client.responses.create = lambda **_kwargs: response

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(result, "OK")

    def test_missing_api_key_returns_actionable_message(self) -> None:
        with patch.object(openai_adapter, "OPENAI_API_KEY", ""):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(
            result,
            "OpenAI connection failed: OPENAI_API_KEY is not configured",
        )

    def test_api_error_returns_cause_without_exposing_api_key(self) -> None:
        api_key = "sk-test-secret-value"

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"invalid API key: {api_key}"),
            ),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertIn("RuntimeError: invalid API key", result)
        self.assertNotIn(api_key, result)

    def test_empty_response_returns_response_diagnostics(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=[],
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(
            result,
            "OpenAI connection failed: response contained no text output "
            "(status=incomplete, reason=max_output_tokens)",
        )

    def test_malformed_response_returns_format_error(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=object(),
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertIn(
            "OpenAI connection failed: invalid Responses API response: TypeError",
            result,
        )


if __name__ == "__main__":
    unittest.main()
