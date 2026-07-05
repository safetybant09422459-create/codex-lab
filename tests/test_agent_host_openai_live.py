import unittest

from backend.config import OPENAI_API_KEY
from backend.live_llm_smoke import run_live_llm_smoke


@unittest.skipUnless(OPENAI_API_KEY, "OPENAI_API_KEY is not configured")
class AgentHostOpenAILiveSmokeTest(unittest.TestCase):
    def test_answer_and_runtime_operation_loop(self) -> None:
        result = run_live_llm_smoke()

        self.assertTrue(result.success, result.to_dict())
        self.assertTrue(result.answer_returned)
        self.assertTrue(result.call_operation_returned)
        self.assertTrue(result.runtime_provider_called)
        self.assertTrue(result.answer_after_observation)


if __name__ == "__main__":
    unittest.main()
