import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.chat_eval import (
    BENCHMARK_VERSION,
    ChatEvalError,
    TravelChatEvaluator,
    build_executive_summary,
    build_improvement_opportunities,
    build_recommended_next_actions,
    build_root_cause_opportunities,
    classify_failure_root_cause,
    classify_failure_layer,
    compare_benchmarks,
    detect_regressions,
    improvement_hint_for_layer,
    load_cases,
    load_benchmark,
    main,
    priority_for_percentage,
    rank_top_improvements,
    render_diff_markdown,
    render_markdown,
    save_baseline,
    summarize_layers,
    summarize_root_causes,
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


def _benchmark_result(
    *, total: int, passed: int, planner: int, search: int, context: int
) -> dict:
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "layer_summary": {
            "travel": {
                "planner": planner,
                "search": search,
                "context": context,
            }
        },
    }


class TravelChatEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_cases()
        self.runtime = FakeRuntimeService()

    def test_mock_mode_runs_fixed_cases_without_live_llm(self) -> None:
        summary = TravelChatEvaluator(runtime=self.runtime).run(
            self.cases, mode="mock"
        )

        self.assertEqual(summary["total"], 57)
        self.assertEqual(summary["passed"], 55)
        self.assertEqual(summary["failed"], 2)
        self.assertEqual(
            summary["failure_categories"]["entity_resolution_missing"], 1
        )
        self.assertEqual(summary["failure_categories"]["context_not_used"], 1)
        self.assertEqual(sum(summary["failure_categories"].values()), 2)
        self.assertEqual(summary["benchmark_version"], "Jarvis Benchmark v0.3")
        self.assertEqual(summary["skill_id"], "travel")
        self.assertEqual(summary["skill_ids"], ["travel"])
        self.assertEqual(summary["layer_summary"]["travel"]["entity_resolution"], 1)
        self.assertEqual(summary["layer_summary"]["travel"]["context"], 1)
        self.assertEqual(summary["top_improvements"][0]["failure_layer"], "entity_resolution")
        self.assertEqual(summary["top_improvements"][0]["count"], 1)
        root_counts = {
            root_cause: item["count"]
            for root_cause, item in summary["root_cause_summary"].items()
            if item["count"]
        }
        self.assertEqual(
            root_counts,
            {
                "ambiguous_expected_but_resolved": 1,
                "context_slot_missing": 1,
            },
        )
        self.assertEqual(
            summary["root_cause_opportunities"][0]["failure_root_cause"],
            "ambiguous_expected_but_resolved",
        )
        self.assertEqual(
            summary["recommended_next_actions"][0]["expected_improvement_count"],
            1,
        )
        opportunity = summary["improvement_opportunities"][0]
        self.assertEqual(opportunity["percentage"], 1.8)
        self.assertEqual(opportunity["priority"], "Low")
        self.assertIn("SearchDocument", opportunity["improvement_candidate"])
        self.assertTrue(opportunity["expected_effect"])
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
        self.assertEqual(trace["resolver"], "travel_entity_resolver")
        self.assertEqual(trace["resolution_status"], "ambiguous")
        self.assertGreater(trace["candidate_count"], 1)
        self.assertIsInstance(trace["top_candidate_score"], float)
        self.assertIn("decision", trace)
        self.assertIn("response_summary", trace)
        self.assertEqual(
            trace["clarification_layer"]["reason"], "multiple_candidates"
        )
        timeline_record = next(
            record for record in summary["records"] if record["id"] == "context_day_two"
        )
        self.assertIn("get_trip", timeline_record["baseline"])
        self.assertIn("get_trip_timeline", timeline_record["baseline"])
        self.assertIn(
            "get_trip_timeline", [call["tool_id"] for call in self.runtime.calls]
        )
        self.assertTrue(all(call["confirmed"] is False for call in self.runtime.calls))
        goal_record = next(
            record
            for record in summary["records"]
            if record["id"] == "goal_summary_fukuoka_natural"
        )
        self.assertEqual(goal_record["actual_goal"], "summarize_trip")

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
                "travel_answer_generation": 7,
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
        self.assertEqual(summary["failures"][0]["skill_id"], "travel")
        self.assertEqual(
            summary["failures"][0]["failure_layer"], "entity_resolution"
        )
        self.assertIn("SearchDocument", summary["failures"][0]["improvement_hint"])
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
        self.assertEqual(payload["benchmark_version"], BENCHMARK_VERSION)
        self.assertIn("layer_summary", payload)
        self.assertIn("top_improvements", payload)
        self.assertIn("root_cause_summary", payload)
        self.assertIn("root_cause_opportunities", payload)
        self.assertIn("recommended_next_actions", payload)
        self.assertIn("failure_root_cause", payload["records"][0])
        self.assertIn("trace", payload["records"][0])
        self.assertIn("# Jarvis Benchmark Report", report)
        self.assertIn("Benchmark Version: `Jarvis Benchmark v0.3`", report)
        self.assertIn("## Layer Summary", report)
        self.assertIn("### Travel (`travel`)", report)
        self.assertIn("## Reason Trace", report)
        self.assertIn("## Failure categories count", report)
        self.assertIn("## 改善ヒント", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Improvement Opportunities", report)
        self.assertIn("## Failure Analysis", report)
        self.assertIn("## Root Cause Summary", report)
        self.assertIn("## Top Root Causes", report)
        self.assertIn("## Failure Details", report)
        self.assertIn("## Recommended Next Actions", report)
        self.assertIn("福岡旅行を開いて", render_markdown(summary))

    def test_failure_layer_and_hint_rules_are_stable(self) -> None:
        expected = {
            "tool_selection_error": "tool_selection",
            "entity_resolution_missing": "entity_resolution",
            "entity_resolution_ambiguous": "entity_resolution",
            "wrong_entity": "search",
            "context_not_used": "context",
            "response_not_human_friendly": "response",
            "unsupported_expected": "planner",
            "runtime_error": "tool_execution",
            "security_violation": "unknown",
        }

        for category, layer in expected.items():
            with self.subTest(category=category):
                self.assertEqual(classify_failure_layer(category), layer)
                self.assertTrue(improvement_hint_for_layer(layer))
        self.assertEqual(classify_failure_layer("future_category"), "unknown")

    def test_layer_summary_and_top_improvements_are_skill_aware(self) -> None:
        records = [
            {"skill_id": "travel", "failure_layer": "search"},
            {"skill_id": "travel", "failure_layer": "search"},
            {"skill_id": "travel", "failure_layer": "context"},
            {"skill_id": "photo", "failure_layer": "response"},
            {"skill_id": "photo", "failure_layer": None},
        ]

        layer_summary = summarize_layers(records)
        top = rank_top_improvements(layer_summary)

        self.assertEqual(layer_summary["travel"]["search"], 2)
        self.assertEqual(layer_summary["travel"]["context"], 1)
        self.assertEqual(layer_summary["photo"]["response"], 1)
        self.assertEqual(layer_summary["photo"]["planner"], 0)
        self.assertEqual(top[0]["skill_id"], "travel")
        self.assertEqual(top[0]["failure_layer"], "search")
        self.assertEqual(top[0]["count"], 2)

    def test_priority_uses_total_case_impact(self) -> None:
        self.assertEqual(priority_for_percentage(20.0), "High")
        self.assertEqual(priority_for_percentage(10.0), "Medium")
        self.assertEqual(priority_for_percentage(9.9), "Low")

        opportunities = build_improvement_opportunities(
            {"travel": {"search": 2, "context": 1}}, total=10
        )
        self.assertEqual(opportunities[0]["priority"], "High")
        self.assertEqual(opportunities[1]["priority"], "Medium")

    def test_root_cause_rules_use_expected_actual_candidates_and_trace(self) -> None:
        common = {
            "question": "旅行を開いて",
            "actual": {"action": "needs_context"},
            "candidates": [],
            "trace": {
                "decision": {"type": "not_found"},
                "search_candidates": [],
            },
            "failure_category": "entity_resolution_missing",
        }
        self.assertEqual(
            classify_failure_root_cause(
                **common,
                expected={"expected_classification": "ambiguous_query"},
            ),
            "query_too_broad",
        )
        self.assertEqual(
            classify_failure_root_cause(
                **{**common, "question": "満喫した旅行"},
                expected={"expected_classification": "memo_derived"},
            ),
            "missing_memo_paraphrase",
        )

    def test_root_cause_summary_has_representatives_and_actions(self) -> None:
        records = [
            {
                "question": "満喫した旅行を見せて",
                "failure_root_cause": "missing_memo_paraphrase",
            },
            {
                "question": "リベンジと書いた旅行を開いて",
                "failure_root_cause": "missing_memo_paraphrase",
            },
            {"question": "成功", "failure_root_cause": None},
        ]
        root_summary = summarize_root_causes(records)
        opportunities = build_root_cause_opportunities(root_summary, total=3)
        actions = build_recommended_next_actions(
            {"root_cause_opportunities": opportunities}
        )

        item = root_summary["missing_memo_paraphrase"]
        self.assertEqual(item["count"], 2)
        self.assertEqual(len(item["representative_questions"]), 2)
        self.assertEqual(item["expected_improvement_count"], 2)
        self.assertEqual(item["difficulty"], "Medium")
        self.assertEqual(actions[0]["failure_root_cause"], "missing_memo_paraphrase")

    def test_benchmark_diff_reports_improvements_and_overall_change(self) -> None:
        baseline = _benchmark_result(
            total=100, passed=70, planner=3, search=12, context=2
        )
        current = _benchmark_result(
            total=100, passed=76, planner=3, search=4, context=1
        )

        diff = compare_benchmarks(baseline, current)

        self.assertEqual(diff["layers"]["planner"]["delta"], 0)
        self.assertEqual(diff["layers"]["search"]["delta"], 8)
        self.assertEqual(diff["layers"]["context"]["delta"], 1)
        self.assertEqual(diff["overall"]["delta_percentage_points"], 6.0)
        self.assertFalse(diff["has_regression"])
        self.assertIn("Search", render_diff_markdown(diff))

    def test_regression_detection_reports_worsened_layers(self) -> None:
        baseline = _benchmark_result(
            total=100, passed=80, planner=1, search=2, context=0
        )
        current = _benchmark_result(
            total=100, passed=75, planner=3, search=2, context=1
        )

        diff = compare_benchmarks(baseline, current)
        regressions = detect_regressions(diff["layers"])

        self.assertTrue(diff["has_regression"])
        self.assertEqual(
            [item["failure_layer"] for item in regressions],
            ["planner", "context"],
        )
        self.assertIn("**Regression**: Planner", render_diff_markdown(diff))

    def test_executive_summary_identifies_highest_impact_work(self) -> None:
        summary = {
            "layer_summary": {
                "travel": {"entity_resolution": 16, "context": 0, "planner": 0}
            },
            "improvement_opportunities": build_improvement_opportunities(
                {
                    "travel": {
                        "entity_resolution": 16,
                        "context": 0,
                        "planner": 0,
                    }
                },
                total=50,
            ),
        }

        executive_summary = build_executive_summary(summary)

        self.assertIn("32.0%", executive_summary[0])
        self.assertTrue(any("Contextは失敗0件" in item for item in executive_summary))
        self.assertTrue(any("Plannerは失敗0件" in item for item in executive_summary))
        self.assertTrue(any("最も効果的" in item for item in executive_summary))

    def test_baseline_save_round_trips_complete_result(self) -> None:
        summary = _benchmark_result(
            total=10, passed=8, planner=1, search=1, context=0
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"

            save_baseline(summary, path)
            loaded = load_benchmark(path)

        self.assertEqual(loaded, summary)

    def test_cli_saves_baseline_during_benchmark_run(self) -> None:
        summary = _benchmark_result(
            total=10, passed=8, planner=1, search=1, context=0
        )
        with tempfile.TemporaryDirectory() as directory:
            baseline_path = Path(directory) / "baseline.json"
            output_path = Path(directory) / "current.json"
            with patch("backend.chat_eval.TravelChatEvaluator") as evaluator, patch(
                "backend.chat_eval.load_cases", return_value=[]
            ):
                evaluator.return_value.run.return_value = summary

                exit_code = main(
                    [
                        "--save-baseline",
                        str(baseline_path),
                        "--format",
                        "json",
                        "--output",
                        str(output_path),
                    ]
                )

            loaded = load_benchmark(baseline_path)

        self.assertEqual(exit_code, 1)
        self.assertEqual(loaded, summary)

    def test_cli_diff_writes_report_and_returns_regression_exit_code(self) -> None:
        baseline = _benchmark_result(
            total=100, passed=80, planner=1, search=2, context=0
        )
        current = _benchmark_result(
            total=100, passed=79, planner=2, search=2, context=0
        )
        with tempfile.TemporaryDirectory() as directory:
            baseline_path = Path(directory) / "baseline.json"
            current_path = Path(directory) / "current.json"
            report_path = Path(directory) / "diff.md"
            save_baseline(baseline, baseline_path)
            save_baseline(current, current_path)

            exit_code = main(
                [
                    "--diff",
                    str(baseline_path),
                    str(current_path),
                    "--format",
                    "markdown",
                    "--output",
                    str(report_path),
                ]
            )
            report = report_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertIn("**Regression**: Planner", report)

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
        markdown = render_markdown(summary)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("plain-eval-secret", serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertNotIn(secret, markdown)
        self.assertNotIn("Bearer", markdown)
        self.assertEqual(
            summary["failure_categories"]["security_violation"], 1
        )

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ChatEvalError):
            TravelChatEvaluator(runtime=self.runtime).run([], mode="invalid")


if __name__ == "__main__":
    unittest.main()
