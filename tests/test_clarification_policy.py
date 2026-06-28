import unittest

from backend.chat_core import ComposeRequest, Plan
from backend.clarification_policy import ClarificationPolicy


class ClarificationPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ClarificationPolicy()
        self.trips = [
            {"id": "old", "title": "ゆい初旅行", "start_date": "2024-07-12"},
            {"id": "first", "title": "まい初旅行", "start_date": "2026-01-28"},
            {"id": "apm", "title": "APM &ドイツの森", "start_date": "2026-05-06"},
            {"id": "suma", "title": "須磨シーワールド", "start_date": "2026-05-08"},
            {"id": "latest", "title": "大阪旅行", "start_date": "2026-05-13"},
        ]

    def request(
        self,
        message: str,
        *,
        outcome: str = "success",
        confidence: str = "low",
    ) -> ComposeRequest:
        return ComposeRequest(
            outcome=outcome,
            user_message=message,
            plan=Plan(intent="read", confidence=confidence),
            tool_id="get_trips",
            runtime_result={"trips": self.trips},
        )

    def test_broad_query_offers_all_runtime_candidates(self) -> None:
        result = self.policy.evaluate(self.request("旅行を開いて"))

        self.assertEqual(result.status, "candidates")
        self.assertEqual(result.reason, "query_too_broad")
        self.assertEqual(result.candidate_list, self.trips)
        self.assertEqual(result.recommended_action, "select_candidate")

    def test_any_trip_offers_latest_three(self) -> None:
        result = self.policy.evaluate(self.request("どれか旅行を開いて"))

        self.assertEqual(
            [candidate["id"] for candidate in result.candidate_list],
            ["latest", "suma", "apm"],
        )

    def test_recent_trip_offers_latest_three_without_low_confidence(self) -> None:
        result = self.policy.evaluate(
            self.request(
                "最近旅行したやつ",
                outcome="not_found",
                confidence="medium",
            )
        )

        self.assertEqual(
            [candidate["id"] for candidate in result.candidate_list],
            ["latest", "suma", "apm"],
        )

    def test_broad_query_does_not_depend_on_planner_confidence(self) -> None:
        result = self.policy.evaluate(
            self.request("旅行見せて", confidence="high")
        )

        self.assertEqual(result.status, "candidates")
        self.assertEqual(result.reason, "query_too_broad")

    def test_explicit_trip_list_remains_a_tool_result(self) -> None:
        result = self.policy.evaluate(
            self.request("旅行一覧を見せて", confidence="high")
        )

        self.assertEqual(result.status, "not_required")

    def test_first_time_query_offers_first_trip_titles(self) -> None:
        result = self.policy.evaluate(
            self.request("初めての旅行を見せて", outcome="not_found")
        )

        self.assertEqual(
            [candidate["id"] for candidate in result.candidate_list],
            ["old", "first"],
        )

    def test_missing_context_asks_for_context_without_candidates(self) -> None:
        result = self.policy.evaluate(
            ComposeRequest(
                outcome="needs_context",
                user_message="それを見せて",
                plan=Plan(intent="read", requires_context=True),
            )
        )

        self.assertEqual(result.status, "clarification_required")
        self.assertEqual(result.reason, "missing_context")
        self.assertEqual(result.recommended_action, "provide_context")
        self.assertEqual(result.candidate_list, [])


if __name__ == "__main__":
    unittest.main()
