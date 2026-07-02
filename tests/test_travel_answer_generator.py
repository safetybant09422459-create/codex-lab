import unittest

from backend.chat_core import (
    AnswerRequest,
    ConversationState,
    ExecutionEvidence,
    ExecutionResult,
    Plan,
)
from backend.travel_answer_generator import TravelAnswerGenerator
from backend.travel_chat_adapter import conversation_state_from_runtime_trip


def generate(
    question: str,
    evidence: list[ExecutionEvidence],
    *,
    answer_mode: str = "summary",
):
    goals = {
        "summary": "summarize_trip",
        "day_summary": "summarize_day",
        "meals": "summarize_meals",
    }
    execution = ExecutionResult(
        execution_status="success",
        evidence=evidence,
    )
    state = conversation_state_from_runtime_trip(
        {"id": "trip-kobe", "title": "神戸旅行"}
    )
    return TravelAnswerGenerator().generate(
        AnswerRequest(
            user_question=question,
            plan=Plan(
                intent="get_trip_timeline",
                goal=goals[answer_mode],
                answer_mode=answer_mode,
                required_evidence=["trip", "timeline"],
            ),
            execution_result=execution,
            conversation_state=state,
            evidence=evidence,
        )
    )


class TravelAnswerGeneratorTest(unittest.TestCase):
    def test_plan_answer_mode_is_primary_classification(self) -> None:
        execution = ExecutionResult(
            execution_status="success",
            evidence=[
                ExecutionEvidence(
                    tool_id="get_trip_timeline",
                    result={"items": [{"display_title": "屋台"}]},
                )
            ],
        )
        result = TravelAnswerGenerator().generate(
            AnswerRequest(
                user_question="福岡旅行について教えて",
                plan=Plan(
                    intent="get_trips",
                    goal="summarize_trip",
                    answer_mode="summary",
                    required_evidence=["trip", "timeline"],
                ),
                execution_result=execution,
                conversation_state=conversation_state_from_runtime_trip(
                    {"id": "trip-fukuoka", "title": "福岡旅行"}
                ),
            )
        )

        self.assertEqual(result.answer_type, "activities")
        self.assertIn("屋台", result.answer)
    def test_answers_what_did_from_timeline_evidence(self) -> None:
        result = generate(
            "神戸旅行って何した？",
            [
                ExecutionEvidence(
                    tool_id="get_trip_timeline",
                    arguments={"trip_id": "trip-kobe"},
                    result={
                        "items": [
                            {"display_title": "須磨シーワールド"},
                            {"display_title": "メリケンパーク"},
                        ]
                    },
                )
            ],
        )

        self.assertEqual(result.answer_type, "activities")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(
            result.answer,
            "神戸旅行では、須磨シーワールド、その後メリケンパークの記録があります。",
        )
        self.assertEqual(len(result.used_evidence), 2)

    def test_answers_what_ate_from_food_evidence_only(self) -> None:
        result = generate(
            "神戸旅行で何食べた？",
            [
                ExecutionEvidence(
                    tool_id="get_trip_timeline",
                    result={
                        "items": [
                            {"display_title": "屋台ラーメン", "category": "spot"},
                            {"display_title": "明石焼き", "category": "food"},
                        ]
                    },
                )
            ],
            answer_mode="meals",
        )

        self.assertEqual(result.answer_type, "food")
        self.assertEqual(
            result.answer,
            "神戸旅行では、食事については明石焼きの記録があります。",
        )
        self.assertEqual(result.used_evidence[0].result["display_title"], "明石焼き")

    def test_answers_numbered_day_using_trip_start_date(self) -> None:
        result = generate(
            "2日目は何した？",
            [
                ExecutionEvidence(
                    tool_id="get_trip",
                    result={"trip": {"start_date": "2026-06-01"}},
                ),
                ExecutionEvidence(
                    tool_id="get_trip_timeline",
                    result={
                        "items": [
                            {"display_title": "水族館", "start_at": "2026-06-01T10:00:00"},
                            {"display_title": "ホテル", "start_at": "2026-06-02T18:00:00"},
                        ]
                    },
                ),
            ],
            answer_mode="day_summary",
        )

        self.assertEqual(result.answer_type, "day")
        self.assertEqual(result.answer, "2日目は、ホテルの記録があります。")
        self.assertEqual(len(result.used_evidence), 1)

    def test_reports_missing_food_without_guessing(self) -> None:
        result = generate(
            "何食べた？",
            [
                ExecutionEvidence(
                    tool_id="get_trip_timeline",
                    result={"items": [{"display_title": "水族館", "category": "spot"}]},
                )
            ],
            answer_mode="meals",
        )

        self.assertEqual(result.answer, "取得できた情報には食事内容は含まれていません。")
        self.assertEqual(result.confidence, "low")
        self.assertEqual(result.used_evidence, [])

    def test_planless_request_does_not_reclassify_user_text(self) -> None:
        result = TravelAnswerGenerator().generate(
            AnswerRequest(
                user_question="何した？",
                execution_result=ExecutionResult(execution_status="success"),
                conversation_state=ConversationState(active_skill="travel"),
            )
        )

        self.assertEqual(result.answer_type, "not_applicable")
        self.assertEqual(result.answer, "")
        self.assertEqual(result.confidence, "low")

    def test_generator_has_no_runtime_or_tool_dependency(self) -> None:
        self.assertEqual(vars(TravelAnswerGenerator()), {})


if __name__ == "__main__":
    unittest.main()
