import json
import tempfile
import unittest
from pathlib import Path

from backend.chat_eval import (
    ChatEvalError,
    TravelChatEvaluator,
    load_cases,
    render_markdown,
    write_reports,
)


class FakeRuntimeService:
    def __init__(self) -> None:
        self.trips = [
            {
                "id": "trip-yui",
                "title": "ゆい初旅行",
                "start_date": "2024-07-12",
                "end_date": "2024-07-12",
                "prefectures": "香川県",
                "outing_type": "day_trip",
                "memo": "おためし香川日帰り",
            },
            {
                "id": "trip-suma",
                "title": "須磨シーワールド",
                "start_date": "2026-05-08",
                "end_date": "2026-05-09",
                "prefectures": "兵庫県",
                "outing_type": "overnight",
                "memo": "須磨シーワールド満喫🐬",
            },
            {
                "id": "trip-mai",
                "title": "まい初旅行",
                "start_date": "2026-01-28",
                "end_date": "2026-01-30",
                "prefectures": "兵庫県",
                "outing_type": "overnight",
                "memo": "ゆいは初APM",
            },
            {
                "id": "trip-beiju",
                "title": "ひいばあ米寿祝い",
                "start_date": "2025-03-29",
                "end_date": "2025-03-30",
                "prefectures": "兵庫県",
                "outing_type": "overnight",
            },
            {
                "id": "trip-fukuoka",
                "title": "福岡旅行",
                "start_date": "2026-04-02",
                "end_date": "2026-04-04",
                "prefectures": "福岡",
                "outing_type": "overnight",
                "memo": "おじちゃんの家に泊まって2回目APM",
            },
            {
                "id": "trip-apm-german-forest",
                "title": "APM &ドイツの森",
                "start_date": "2026-05-06",
                "end_date": "2026-05-06",
                "prefectures": "岡山県",
                "outing_type": "day_trip",
                "memo": "結婚記念日雨でネモフィラ見れなかったのでリベンジ",
            },
            {
                "id": "trip-osaka",
                "title": "大阪旅行",
                "start_date": "2026-05-13",
                "end_date": "2026-05-15",
                "prefectures": "大阪府",
                "outing_type": "overnight",
            },
        ]
        self.calls = []

    def execute_stub(self, tool_id, params, confirmed=False, role=None):
        self.calls.append(
            {
                "tool_id": tool_id,
                "params": params,
                "confirmed": confirmed,
                "role": role,
            }
        )
        if tool_id == "get_trips":
            result = {"trips": self.trips, "source": "eval_fixture"}
        elif tool_id == "get_trip":
            trip = next(
                (trip for trip in self.trips if trip["id"] == params.get("trip_id")),
                None,
            )
            result = {"trip": trip, "timeline": [], "source": "eval_fixture"}
        elif tool_id == "get_trip_timeline":
            result = {
                "trip_id": params.get("trip_id"),
                "timeline": [{"day": 2, "title": "屋台"}],
                "source": "eval_fixture",
            }
        else:
            return {"success": False, "result": None}
        return {"success": True, "result": result}


class TravelChatEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_cases()
        self.runtime = FakeRuntimeService()

    def test_mock_mode_runs_fixed_cases_without_live_llm(self) -> None:
        summary = TravelChatEvaluator(runtime=self.runtime).run(
            self.cases, mode="mock"
        )

        self.assertEqual(summary["total"], 50)
        self.assertEqual(summary["passed"], 33)
        self.assertEqual(summary["failed"], 17)
        self.assertEqual(
            summary["failure_categories"]["entity_resolution_missing"], 16
        )
        self.assertEqual(summary["failure_categories"]["context_not_used"], 1)
        self.assertEqual(sum(summary["failure_categories"].values()), 17)
        self.assertTrue(
            all("debug_steps" in record for record in summary["records"])
        )
        self.assertTrue(all("trace" in record for record in summary["records"]))
        trace = next(
            record["trace"]
            for record in summary["records"]
            if record["id"] == "location_kobe_candidates"
        )
        self.assertEqual(trace["planner"]["proposed_tool"], "get_trips")
        self.assertTrue(trace["runtime_steps"])
        self.assertTrue(trace["search_candidates"])
        self.assertIn("score", trace["search_candidates"][0])
        self.assertIn("matched_by", trace["search_candidates"][0])
        self.assertIn("decision", trace)
        self.assertIn("response_summary", trace)
        timeline_record = next(
            record for record in summary["records"] if record["id"] == "context_day_two"
        )
        self.assertIn("get_trip", timeline_record["baseline"])
        self.assertIn("get_trip_timeline", timeline_record["baseline"])
        self.assertIn(
            "get_trip_timeline", [call["tool_id"] for call in self.runtime.calls]
        )
        self.assertTrue(all(call["confirmed"] is False for call in self.runtime.calls))

    def test_cases_cover_requested_classifications(self) -> None:
        counts = {}
        for case in self.cases:
            classification = case.get("expected_classification")
            counts[classification] = counts.get(classification, 0) + 1

        self.assertEqual(
            counts,
            {
                "trip_title_or_partial_title": 10,
                "prefecture_or_location": 8,
                "memo_derived": 8,
                "date_year_or_duration": 8,
                "context_follow_up": 7,
                "ambiguous_query": 5,
                "unsupported_or_needs_experience_context": 4,
            },
        )

    def test_failure_summary_classifies_entity_resolution(self) -> None:
        cases = [dict(self.cases[0], expected_trip_title="別の旅行")]

        summary = TravelChatEvaluator(runtime=self.runtime).run(cases, mode="mock")

        self.assertEqual(summary["failed"], 1)
        self.assertEqual(
            summary["failures"][0]["category"], "entity_resolution_missing"
        )
        self.assertEqual(summary["failure_categories"]["entity_resolution_missing"], 1)
        self.assertIn("question", summary["failures"][0])
        self.assertIn("expected", summary["failures"][0])
        self.assertIn("actual", summary["failures"][0])

    def test_live_mode_does_not_inject_mock_proposal(self) -> None:
        observed = {}

        def handler(message, **kwargs):
            observed.update(kwargs)
            return {
                "action": "tool_result",
                "tool_id": "get_trips",
                "arguments": {},
                "reply": "ok",
                "result": {"trips": []},
                "debug": {"steps": []},
            }

        TravelChatEvaluator(runtime=self.runtime, chat_handler=handler).run(
            [self.cases[0]], mode="live"
        )

        self.assertIsNone(observed["text_generator"])
        self.assertIs(observed["runtime"], self.runtime)

    def test_json_and_markdown_reports_are_written(self) -> None:
        summary = TravelChatEvaluator(runtime=self.runtime).run(
            [self.cases[0]], mode="mock"
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "summary.json"
            markdown_path = Path(directory) / "report.md"
            write_reports(
                summary, json_path=json_path, markdown_path=markdown_path
            )

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            report = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(payload["total"], 1)
        self.assertIn("trace", payload["records"][0])
        self.assertIn("# Travel Chat Eval Report", report)
        self.assertIn("## Reason Trace", report)
        self.assertIn("## Failure categories count", report)
        self.assertIn("## 改善ヒント", report)
        self.assertIn("福岡旅行を開いて", render_markdown(summary))

    def test_trace_redacts_secrets(self) -> None:
        secret = "sk-eval-secret-value"

        def handler(_message, **_kwargs):
            return {
                "action": "runtime_error",
                "reply": f"Bearer {secret}",
                "debug": {
                    "steps": [
                        {
                            "tool_id": "get_trips",
                            "detail": secret,
                            "api_key": "plain-eval-secret",
                        }
                    ]
                },
            }

        summary = TravelChatEvaluator(
            runtime=self.runtime, chat_handler=handler
        ).run([self.cases[0]], mode="live")
        serialized = json.dumps(summary, ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("plain-eval-secret", serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertEqual(
            summary["failure_categories"]["security_violation"], 1
        )

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ChatEvalError):
            TravelChatEvaluator(runtime=self.runtime).run([], mode="invalid")


if __name__ == "__main__":
    unittest.main()
