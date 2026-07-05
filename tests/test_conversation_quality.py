import unittest
from unittest.mock import patch

from backend.basic_chat import handle_basic_chat


class BasicChatFallbackTest(unittest.TestCase):
    """Legacy fallback stays Tool-free and is not the /api/chat route."""

    def test_greeting_remains_a_direct_llm_answer(self) -> None:
        result = handle_basic_chat(
            "こんにちは", text_generator=lambda **_: ("こんにちは。", None)
        )
        self.assertEqual(result, {"action": "direct_answer", "reply": "こんにちは。"})

    def test_travel_request_cannot_trigger_runtime_from_legacy_fallback(self) -> None:
        result = handle_basic_chat(
            "福岡旅行を開いて",
            text_generator=lambda **_: (
                "Travel操作は現在Chatから利用できません。",
                None,
            ),
        )
        self.assertEqual(result["action"], "direct_answer")
        self.assertNotIn("tool_id", result)
        self.assertNotIn("result", result)

    def test_generation_failure_is_explicit_and_tool_free(self) -> None:
        with patch(
            "backend.basic_chat.generate_text_with_timings",
            side_effect=RuntimeError("unavailable"),
        ):
            result = handle_basic_chat("旅行一覧を見せて", debug=True)
        self.assertEqual(result["action"], "direct_answer")
        self.assertTrue(result["debug"]["fallback"])
        self.assertNotIn("tool_id", result)


if __name__ == "__main__":
    unittest.main()
