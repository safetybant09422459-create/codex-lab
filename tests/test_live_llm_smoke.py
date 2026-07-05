import unittest

from backend.agent_host import AgentContractError
from backend.live_llm_smoke import _failure_category
from backend.openai_adapter import (
    OpenAIIncompleteResponseError,
    OpenAIModelRefusalError,
    OpenAIResponseValidationError,
    OpenAITimeoutError,
)


class LiveLLMSmokeTest(unittest.TestCase):
    def test_failure_categories_are_distinct(self) -> None:
        cases = (
            (OpenAIResponseValidationError("invalid"), "schema_violation"),
            (AgentContractError("invalid"), "schema_violation"),
            (OpenAITimeoutError("timeout"), "timeout"),
            (OpenAIModelRefusalError("refused"), "model_refusal"),
            (OpenAIIncompleteResponseError("incomplete"), "incomplete"),
        )

        for error, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(_failure_category(error), expected)


if __name__ == "__main__":
    unittest.main()
