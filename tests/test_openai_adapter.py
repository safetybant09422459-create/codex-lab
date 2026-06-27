import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import openai_adapter


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
