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
