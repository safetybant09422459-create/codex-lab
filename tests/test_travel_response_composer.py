import unittest

from backend.chat_core import AnswerResult, ComposeRequest, Plan
from backend.travel_chat_adapter import conversation_state_from_legacy_context
from backend.travel_response_composer import TravelResponseComposer


class TravelResponseComposerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = TravelResponseComposer()

    def test_trip_list_keeps_legacy_shape_and_builds_v1_block(self) -> None:
        runtime_result = {"trips": [{"id": "trip-1", "title": "福岡旅行"}]}

        composed = self.composer.compose(
            ComposeRequest(
                outcome="success",
                tool_id="get_trips",
                arguments={},
                runtime_result=runtime_result,
            )
        )

        self.assertEqual(
            composed.response,
            {
                "action": "tool_result",
                "tool_id": "get_trips",
                "arguments": {},
                "reply": "旅行一覧を取得しました。",
                "result": runtime_result,
            },
        )
        self.assertEqual(
            composed.response_v1.content_blocks[0].type,
            "travel_trip_list",
        )

    def test_trip_detail_builds_navigation_and_verified_context(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}

        composed = self.composer.compose(
            ComposeRequest(
                outcome="success",
                tool_id="get_trip",
                arguments={"trip_id": "trip-fukuoka"},
                runtime_result={"trip": trip},
            )
        )

        self.assertEqual(composed.response["reply"], "福岡旅行を開きます。")
        self.assertEqual(
            composed.response["navigation"],
            {
                "type": "travel_trip",
                "target": "#travel?trip_id=trip-fukuoka",
                "trip_id": "trip-fukuoka",
                "label": "Travelで開く",
            },
        )
        self.assertEqual(
            composed.conversation_state.selected_entities[0].entity_id,
            "trip-fukuoka",
        )
        self.assertEqual(
            composed.response_v1.suggested_actions[0].type,
            "navigate",
        )

    def test_trip_detail_keeps_navigation_with_llm_final_answer(self) -> None:
        composed = self.composer.compose(
            ComposeRequest(
                outcome="success",
                tool_id="get_trip",
                arguments={"trip_id": "trip-fukuoka"},
                runtime_result={
                    "trip": {"id": "trip-fukuoka", "title": "福岡旅行"}
                },
                answer_result=AnswerResult(
                    answer="福岡旅行を開きます。",
                    confidence="high",
                    answer_type="grounded",
                    source="llm",
                    evidence_used=True,
                ),
            )
        )

        self.assertEqual(composed.response["reply"], "福岡旅行を開きます。")
        self.assertEqual(composed.response["navigation"]["trip_id"], "trip-fukuoka")

    def test_candidates_keep_legacy_candidate_response(self) -> None:
        candidates = [
            {"id": "trip-1", "title": "神戸旅行"},
            {"id": "trip-2", "title": "神戸旅行 2"},
        ]

        composed = self.composer.compose(
            ComposeRequest(outcome="candidates", candidates=candidates)
        )

        self.assertEqual(composed.response["action"], "needs_context")
        self.assertEqual(
            composed.response["reply"], "2件の候補があります。どれを開きますか？"
        )
        self.assertEqual(composed.response["candidates"], candidates)
        self.assertEqual(
            composed.response["clarification"],
            {
                "status": "candidates",
                "clarification": "2件の候補があります。どれを開きますか？",
                "candidate_list": candidates,
                "reason": "multiple_candidates",
                "recommended_action": "select_candidate",
            },
        )
        self.assertEqual(
            composed.response_v1.content_blocks[0].type,
            "travel_trip_candidates",
        )

    def test_not_found_can_clear_unverified_selected_trip(self) -> None:
        state = conversation_state_from_legacy_context(
            {"selected_trip_id": "missing", "selected_trip_title": "不明な旅行"}
        )

        composed = self.composer.compose(
            ComposeRequest(
                outcome="not_found",
                conversation_state=state,
                clear_context_on_not_found=True,
            )
        )

        self.assertEqual(
            composed.response,
            {"action": "needs_context", "reply": "該当する旅行が見つかりませんでした。"},
        )
        self.assertEqual(composed.conversation_state.selected_entities, [])

    def test_pending_write_is_descriptive_and_does_not_execute(self) -> None:
        composed = self.composer.compose(
            ComposeRequest(
                outcome="pending_write",
                tool_id="update_experience",
                arguments={"experience_id": "experience-1", "memo": "更新"},
            )
        )

        self.assertEqual(
            composed.response,
            {
                "action": "pending_write_not_implemented",
                "tool_id": "update_experience",
                "arguments": {"experience_id": "experience-1", "memo": "更新"},
                "reply": "更新操作には確認が必要です。現在は提案のみ対応しています。",
            },
        )

    def test_photo_goal_explains_missing_evidence_instead_of_generic_support(self) -> None:
        composed = self.composer.compose(
            ComposeRequest(
                outcome="needs_context",
                plan=Plan(
                    intent="needs_context",
                    goal="show_photos",
                    answer_mode="photos",
                    required_evidence=["trip", "experience", "photo"],
                    requires_context=True,
                    reason=(
                        "アンパンマンミュージアムの写真を探すには、"
                        "対象体験の写真連携が必要です。"
                    ),
                ),
            )
        )

        self.assertIn("アンパンマンミュージアム", composed.response["reply"])
        self.assertIn("対象体験の写真連携", composed.response["reply"])


if __name__ == "__main__":
    unittest.main()
