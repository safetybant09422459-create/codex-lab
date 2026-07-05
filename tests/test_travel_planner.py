import json
import unittest

from backend.chat_core import (
    ConversationState,
    ConversationTurn,
    ConversationWorkingContext,
    EntityRef,
    Plan,
    Planner,
)
from backend.travel_planner import TravelPlanner, legacy_proposal_from_plan


def json_generator(payload: dict[str, object]):
    def generate(**_kwargs: str) -> str:
        if not {"goal", "answer_mode", "required_evidence"}.issubset(payload):
            payload.update(
                goal="open_trip",
                answer_mode="none",
                required_evidence=["trip"],
            )
        return json.dumps(payload, ensure_ascii=False)

    return generate


class PlanContractTest(unittest.TestCase):
    def test_plan_defaults_are_descriptive_and_extensible(self) -> None:
        plan = Plan(intent="show_trips", target_skill="travel")

        self.assertEqual(plan.goal, "clarify")
        self.assertEqual(plan.answer_mode, "none")
        self.assertEqual(plan.required_evidence, [])
        self.assertEqual(plan.tool_candidates, [])
        self.assertFalse(plan.requires_resolution)
        self.assertFalse(plan.requires_context)
        self.assertFalse(plan.requires_confirmation)
        self.assertIsNone(plan.target_entity_type)


class TravelPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.planner: Planner = TravelPlanner()

    def test_planner_v1_proposal_is_rejected_without_python_defaults(self) -> None:
        plan = self.planner.create_plan(
            "旅行一覧を見せて",
            text_generator=lambda **_: json.dumps(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        self.assertTrue(plan.requires_context)
        self.assertEqual(plan.tool_candidates, [])

    def test_valid_llm_proposal_is_converted_to_plan(self) -> None:
        plan = self.planner.create_plan(
            "旅行一覧を見せて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "goal": "open_trip",
                    "answer_mode": "none",
                    "required_evidence": ["trip"],
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        self.assertEqual(plan.intent, "get_trips")
        self.assertEqual(plan.target_skill, "travel")
        self.assertEqual(plan.target_entity_type, "trip")
        self.assertEqual(len(plan.tool_candidates), 1)
        self.assertEqual(plan.tool_candidates[0].tool_id, "get_trips")
        self.assertEqual(plan.tool_candidates[0].arguments, {})
        self.assertEqual(plan.confidence, "high")
        self.assertEqual(plan.reason, "旅行一覧を取得します。")
        self.assertFalse(plan.requires_context)
        self.assertFalse(plan.requires_confirmation)

    def test_named_open_trip_keeps_open_goal(self) -> None:
        plan = self.planner.create_plan(
            "福岡旅行を開いて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "goal": "open_trip",
                    "answer_mode": "none",
                    "required_evidence": ["trip"],
                    "tool_id": "get_trips",
                    "arguments": {},
                    "entity_query": "福岡旅行",
                    "confidence": "medium",
                    "reply": "福岡旅行を探します。",
                }
            ),
        )

        self.assertEqual(plan.goal, "open_trip")
        self.assertEqual(plan.answer_mode, "none")
        self.assertEqual(plan.required_evidence, ["trip"])

    def test_prompt_contains_question_history_and_conversation_state(self) -> None:
        observed = {}

        def generate(**kwargs: str) -> str:
            observed.update(kwargs)
            return json.dumps(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "medium",
                    "reply": "大阪旅行を探します。",
                },
                ensure_ascii=False,
            )

        self.planner.create_plan(
            "大阪で何食べた？",
            conversation=ConversationWorkingContext(
                turns=[
                    ConversationTurn(
                        role="user", content="神戸の博物館で何した？"
                    ),
                    ConversationTurn(role="assistant", content="展示を見ました。"),
                ]
            ),
            conversation_state=ConversationState(
                active_skill="travel",
                selected_entities=[
                    EntityRef(
                        skill_id="travel",
                        entity_type="trip",
                        entity_id="trip-kobe",
                        label="神戸旅行",
                        source="test",
                    )
                ],
                skill_slots={"travel": {"selected_trip_title": "神戸旅行"}},
            ),
            text_generator=generate,
        )

        prompt = observed["input_text"]
        self.assertLess(
            prompt.index("Current question:"), prompt.index("Conversation history")
        )
        self.assertLess(
            prompt.index("Conversation history"), prompt.index("ConversationState")
        )
        self.assertIn("大阪で何食べた？", prompt)
        self.assertIn('"role":"user"', prompt)
        self.assertIn("神戸の博物館で何した？", prompt)
        self.assertIn("trip-kobe", prompt)

    def test_prompt_accepts_no_history_and_no_state(self) -> None:
        observed = {}

        def generate(**kwargs: str) -> str:
            observed.update(kwargs)
            return json.dumps(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                },
                ensure_ascii=False,
            )

        self.planner.create_plan("旅行一覧を見せて", text_generator=generate)

        self.assertIn("Conversation history", observed["input_text"])
        self.assertIn("[]", observed["input_text"])
        self.assertTrue(
            observed["input_text"].endswith(
                '{"active_skill":"travel","selected_entities":[],"skill_slots":{}}'
            )
        )

    def test_needs_context_proposal_has_no_tool_candidate(self) -> None:
        plan = self.planner.create_plan(
            "写真を見せて",
            text_generator=json_generator(
                {
                    "action": "needs_context",
                    "goal": "show_photos",
                    "answer_mode": "photos",
                    "required_evidence": ["trip", "experience", "photo"],
                    "reply": "写真を探すには、対象体験の写真連携が必要です。",
                }
            ),
        )

        self.assertEqual(plan.intent, "needs_context")
        self.assertTrue(plan.requires_context)
        self.assertEqual(plan.tool_candidates, [])
        self.assertEqual(plan.goal, "show_photos")
        self.assertEqual(plan.answer_mode, "photos")
        self.assertEqual(plan.required_evidence, ["trip", "experience", "photo"])
        self.assertEqual(
            plan.reason,
            "写真を探すには、対象体験の写真連携が必要です。",
        )

    def test_goal_aware_question_forms_use_current_utterance(self) -> None:
        cases = (
            (
                "福岡旅行なにした？",
                "summarize_trip",
                "summary",
                ["trip", "timeline"],
            ),
            (
                "福岡の旅行で2日目何した？",
                "summarize_day",
                "day_summary",
                ["trip", "timeline"],
            ),
            (
                "福岡旅行のご飯何食べた？",
                "summarize_meals",
                "meals",
                ["trip", "timeline"],
            ),
        )
        stale_state = ConversationState(
            active_skill="travel",
            selected_entities=[
                EntityRef(
                    skill_id="travel",
                    entity_type="trip",
                    entity_id="trip-kobe",
                    label="神戸旅行",
                    source="test",
                )
            ],
        )

        for question, goal, answer_mode, evidence in cases:
            with self.subTest(question=question):
                plan = self.planner.create_plan(
                    question,
                    conversation_state=stale_state,
                    text_generator=json_generator(
                        {
                            "action": "tool_proposal",
                            "goal": goal,
                            "answer_mode": answer_mode,
                            "required_evidence": evidence,
                            "tool_id": "get_trips",
                            "arguments": {},
                            "entity_query": "福岡旅行",
                            "confidence": "medium",
                            "reply": "旅行を探します。",
                        }
                    ),
                )
                self.assertEqual(plan.goal, goal)
                self.assertEqual(plan.answer_mode, answer_mode)
                self.assertEqual(plan.required_evidence, evidence)
                self.assertEqual(plan.tool_candidates[0].tool_id, "get_trips")

    def test_named_photo_request_is_preserved_as_show_photos_goal(self) -> None:
        plan = self.planner.create_plan(
            "アンパンマンミュージアムの写真見せて",
            text_generator=json_generator(
                {
                    "action": "needs_context",
                    "goal": "show_photos",
                    "answer_mode": "photos",
                    "required_evidence": ["trip", "experience", "photo"],
                    "reply": (
                        "アンパンマンミュージアムの写真を探すには、"
                        "対象体験の写真連携が必要です。"
                    ),
                }
            ),
        )

        self.assertEqual(plan.goal, "show_photos")
        self.assertEqual(plan.answer_mode, "photos")
        self.assertTrue(plan.requires_context)
        self.assertIn("アンパンマンミュージアム", plan.reason)

    def test_current_named_subject_is_carried_as_resolution_query(self) -> None:
        plan = self.planner.create_plan(
            "大阪で何食べた？",
            conversation_state=ConversationState(
                active_skill="travel",
                selected_entities=[
                    EntityRef(
                        skill_id="travel",
                        entity_type="trip",
                        entity_id="trip-kobe",
                        label="神戸旅行",
                        source="test",
                    )
                ],
            ),
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "goal": "summarize_meals",
                    "answer_mode": "meals",
                    "required_evidence": ["trip", "timeline"],
                    "tool_id": "get_trips",
                    "arguments": {},
                    "entity_query": "大阪",
                    "confidence": "medium",
                    "reply": "大阪旅行を探します。",
                }
            ),
        )

        self.assertEqual(plan.goal, "summarize_meals")
        self.assertEqual(plan.tool_candidates[0].tool_id, "get_trips")
        self.assertEqual(plan.tool_candidates[0].arguments, {})
        self.assertEqual(plan.resolution_query, "大阪")

    def test_inconsistent_goal_contract_falls_back_safely(self) -> None:
        plan = self.planner.create_plan(
            "何食べた？",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "goal": "summarize_meals",
                    "answer_mode": "summary",
                    "required_evidence": ["trip"],
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行を探します。",
                }
            ),
        )

        self.assertEqual(plan.intent, "needs_context")
        self.assertTrue(plan.requires_context)

    def test_write_proposal_only_marks_confirmation_requirement(self) -> None:
        plan = self.planner.create_plan(
            "メモを更新して",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "update_experience",
                    "arguments": {
                        "experience_id": "experience-1",
                        "memo": "楽しかった",
                    },
                    "confidence": "high",
                    "reply": "体験を更新します。",
                }
            ),
        )

        self.assertTrue(plan.requires_confirmation)
        self.assertEqual(plan.tool_candidates[0].tool_id, "update_experience")

    def test_invalid_llm_output_becomes_context_plan(self) -> None:
        plan = self.planner.create_plan(
            "旅行一覧を見せて",
            text_generator=lambda **_kwargs: "not-json",
        )

        self.assertEqual(plan.intent, "needs_context")
        self.assertTrue(plan.requires_context)
        self.assertEqual(plan.tool_candidates, [])

    def test_plan_adapter_preserves_legacy_proposal_contract(self) -> None:
        plan = self.planner.create_plan(
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

        proposal = legacy_proposal_from_plan(plan, debug=True)

        self.assertEqual(proposal["action"], "tool_proposal")
        self.assertEqual(proposal["tool_id"], "get_trips")
        self.assertIn("timings_ms", proposal["debug"])


if __name__ == "__main__":
    unittest.main()
