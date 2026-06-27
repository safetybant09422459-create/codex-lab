import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import chat_orchestrator, openai_adapter
from backend.chat_tool_policy import CHAT_TRAVEL_TOOL_ALLOWLIST


def json_generator(payload: dict[str, object]):
    def generate(**_kwargs: str) -> str:
        return json.dumps(payload, ensure_ascii=False)

    return generate


class ChatOrchestratorTest(unittest.TestCase):
    def test_trip_list_proposes_get_trips(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=False,
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        self.assertEqual(
            result,
            {
                "action": "tool_proposal",
                "tool_id": "get_trips",
                "arguments": {},
                "confidence": "high",
                "reply": "旅行一覧を取得します。",
            },
        )
        self.assertNotIn("debug", result)

    def test_debug_includes_numeric_timings(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=True,
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        timings = result["debug"]["timings_ms"]
        self.assertEqual(
            set(timings),
            {
                "build_prompt",
                "llm_call",
                "json_parse",
                "policy_validation",
                "fallback",
                "total",
            },
        )
        self.assertTrue(
            all(isinstance(value, (int, float)) for value in timings.values())
        )

    def test_api_error_debug_still_includes_total(self) -> None:
        def raise_api_error(**_kwargs: str) -> str:
            raise openai_adapter.OpenAIRequestError("safe failure")

        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=True,
            text_generator=raise_api_error,
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertIsInstance(result["debug"]["timings_ms"]["total"], float)
        self.assertGreaterEqual(result["debug"]["timings_ms"]["fallback"], 0)

    def test_default_adapter_error_debug_keeps_safe_timings(self) -> None:
        adapter_timings = {
            "api_call": 12.3,
            "response_text_extraction": 0.0,
            "total": 12.4,
        }

        with patch.object(
            chat_orchestrator,
            "generate_text_with_timings",
            side_effect=openai_adapter.OpenAIRequestError(
                "safe failure", timings_ms=adapter_timings
            ),
        ):
            result = chat_orchestrator.propose_travel_tool(
                "旅行一覧を見せて",
                debug=True,
            )

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(
            result["debug"]["openai_adapter"]["timings_ms"],
            adapter_timings,
        )

    def test_debug_includes_openai_adapter_timings_for_default_generator(self) -> None:
        payload = json.dumps(
            {
                "action": "needs_context",
                "reply": "対象を指定してください。",
            },
            ensure_ascii=False,
        )
        adapter_timings = {
            "api_call": 12.3,
            "response_text_extraction": 0.2,
            "total": 12.6,
        }

        with patch.object(
            chat_orchestrator,
            "generate_text_with_timings",
            return_value=(payload, adapter_timings),
        ):
            result = chat_orchestrator.propose_travel_tool(
                "旅行一覧を見せて",
                debug=True,
            )

        self.assertEqual(
            result["debug"]["openai_adapter"]["timings_ms"],
            adapter_timings,
        )

    def test_debug_does_not_expose_secrets_or_model_content(self) -> None:
        secret = "sk-debug-secret-value"

        def raise_secret_error(**_kwargs: str) -> str:
            raise RuntimeError(f"Bearer {secret} response body secret-response")

        result = chat_orchestrator.propose_travel_tool(
            f"Bearer {secret}",
            debug=True,
            text_generator=raise_secret_error,
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("secret-response", serialized)

    def test_named_trip_proposes_get_trips_without_inventing_id(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "福岡旅行を開いて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "medium",
                    "reply": "福岡旅行を探します。",
                }
            ),
        )

        self.assertEqual(result["tool_id"], "get_trips")
        self.assertEqual(result["arguments"], {})
        self.assertEqual(result["confidence"], "medium")

    def test_photo_request_without_experience_context_is_supported(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "アンパンマンミュージアムの写真見せて",
            text_generator=json_generator(
                {
                    "action": "needs_context",
                    "reply": "どの旅行の体験か確認するため、旅行または体験を先に選んでください。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")

    def test_tool_outside_allowlist_is_rejected(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "場所を一覧にして",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_spots",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "場所を取得します。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertNotIn("tool_id", result)
        self.assertNotIn("get_spots", CHAT_TRAVEL_TOOL_ALLOWLIST)

    def test_update_experience_rejects_arguments_outside_chat_policy(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "体験のメモとタイトルを変えて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "update_experience",
                    "arguments": {
                        "experience_id": "experience-1",
                        "memo": "楽しかった",
                        "display_title": "変更後",
                    },
                    "confidence": "high",
                    "reply": "体験を更新します。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertNotIn("arguments", result)

    def test_non_json_model_response_falls_back_safely(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            text_generator=lambda **_kwargs: "旅行一覧を取得します。",
        )

        self.assertEqual(result["action"], "needs_context")

    def test_api_key_is_redacted_from_input_and_output(self) -> None:
        api_key = "sk-test-secret-value"
        captured: dict[str, str] = {}

        def generate(**kwargs: str) -> str:
            captured.update(kwargs)
            return json.dumps(
                {
                    "action": "needs_context",
                    "reply": f"確認が必要です: {api_key}",
                }
            )

        with patch.object(openai_adapter, "OPENAI_API_KEY", api_key):
            result = chat_orchestrator.propose_travel_tool(
                f"この値を使って: Bearer token-value {api_key}",
                text_generator=generate,
            )

        serialized_result = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(api_key, captured["input_text"])
        self.assertNotIn("token-value", captured["input_text"])
        self.assertNotIn(api_key, serialized_result)

    def test_runtime_is_not_imported_or_called(self) -> None:
        source = Path("backend/chat_orchestrator.py").read_text(encoding="utf-8")

        self.assertNotIn("RuntimeService", source)
        self.assertNotIn("execute_stub", source)
        self.assertNotIn("runtime.execute", source)


if __name__ == "__main__":
    unittest.main()
