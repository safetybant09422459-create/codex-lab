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
        return json.dumps(payload, ensure_ascii=False)

    return generate


class PlanContractTest(unittest.TestCase):
    def test_plan_defaults_are_descriptive_and_extensible(self) -> None:
        plan = Plan(intent="show_trips", target_skill="travel")

        self.assertEqual(plan.tool_candidates, [])
        self.assertFalse(plan.requires_resolution)
        self.assertFalse(plan.requires_context)
        self.assertFalse(plan.requires_confirmation)
        self.assertIsNone(plan.target_entity_type)


class TravelPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.planner: Planner = TravelPlanner()

    def test_valid_llm_proposal_is_converted_to_plan(self) -> None:
        plan = self.planner.create_plan(
            "旅行一覧を見せて",
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
                    "reply": "対象を指定してください。",
                }
            ),
        )

        self.assertEqual(plan.intent, "needs_context")
        self.assertTrue(plan.requires_context)
        self.assertEqual(plan.tool_candidates, [])
        self.assertEqual(plan.reason, "対象を指定してください。")

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
