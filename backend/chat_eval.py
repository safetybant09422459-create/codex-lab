from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .chat_orchestrator import handle_travel_chat
from .config import ROOT_DIR
from .openai_adapter import redact_sensitive_text
from .runtime import RuntimeService
from .travel_search_index import TravelSearchIndex


DEFAULT_CASES_PATH = ROOT_DIR / "evals" / "travel_chat_cases.json"
BENCHMARK_VERSION = "Jarvis Benchmark v0.3"
FAILURE_CATEGORIES = (
    "tool_selection_error",
    "entity_resolution_missing",
    "entity_resolution_ambiguous",
    "wrong_entity",
    "context_not_used",
    "response_not_human_friendly",
    "unsupported_expected",
    "runtime_error",
    "security_violation",
)
FAILURE_LAYERS = (
    "planner",
    "entity_resolution",
    "search",
    "tool_selection",
    "tool_execution",
    "context",
    "response",
    "ui",
    "unknown",
)
FAILURE_ROOT_CAUSES = (
    "query_too_broad",
    "missing_semantic_match",
    "missing_memo_paraphrase",
    "missing_experience_search",
    "ambiguous_expected_but_resolved",
    "context_slot_missing",
    "benchmark_expectation_mismatch",
    "unsupported_intent",
    "unknown",
)

_ROOT_CAUSE_GUIDANCE = {
    "query_too_broad": {
        "improvement_candidate": "clarification question / candidate fallback policy",
        "difficulty": "Low",
    },
    "missing_semantic_match": {
        "improvement_candidate": "semantic search / synonym and paraphrase handling",
        "difficulty": "Medium",
    },
    "missing_memo_paraphrase": {
        "improvement_candidate": "semantic search / embedding / memo synonym handling",
        "difficulty": "Medium",
    },
    "missing_experience_search": {
        "improvement_candidate": "experience search source and intent routing",
        "difficulty": "High",
    },
    "ambiguous_expected_but_resolved": {
        "improvement_candidate": "candidate expectation policy and resolved-result acceptance review",
        "difficulty": "Low",
    },
    "context_slot_missing": {
        "improvement_candidate": "ConversationState slot expansion",
        "difficulty": "Medium",
    },
    "benchmark_expectation_mismatch": {
        "improvement_candidate": "benchmark expectation and valid-outcome policy review",
        "difficulty": "Low",
    },
    "unsupported_intent": {
        "improvement_candidate": "supported-intent scope and fallback response definition",
        "difficulty": "High",
    },
    "unknown": {
        "improvement_candidate": "Reason Trace review and root-cause rule addition",
        "difficulty": "High",
    },
}

_FAILURE_CATEGORY_LAYERS = {
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

_IMPROVEMENT_HINTS = {
    "planner": "Plannerのintent判定ルールと計画例を見直す。",
    "entity_resolution": "SearchDocumentへ地域情報・別名・識別属性を追加する。",
    "search": "検索候補のrankingと一致根拠を見直す。",
    "tool_selection": "PlannerのTool選択ルールを改善する。",
    "tool_execution": "Tool引数、Runtime step、失敗処理を見直す。",
    "context": "ConversationStateへ解決済みEntityを保持する。",
    "response": "Response Composerと返答テンプレートを改善する。",
    "ui": "UIの状態表示と操作導線を改善する。",
    "unknown": "Reason Traceを確認し、失敗レイヤーの判定ルールを追加する。",
}

_EXPECTED_EFFECTS = {
    "planner": "未対応intentの判定精度と計画成功率の向上",
    "entity_resolution": "対象Entityを必要とする検索の成功率向上",
    "search": "検索結果の適合率と正しいEntity選択率の向上",
    "tool_selection": "適切なToolへ到達する割合の向上",
    "tool_execution": "Tool実行成功率と障害時の回復性向上",
    "context": "会話継続時の文脈利用成功率向上",
    "response": "回答の可読性と利用者の理解度向上",
    "ui": "状態把握と操作完了率の向上",
    "unknown": "未分類失敗の可視化と改善対象の特定",
}


class ChatEvalError(ValueError):
    pass


class FixedProposalGenerator:
    """Return case-owned LLM proposals without making an external API call."""

    def __init__(self, proposal: dict[str, Any]) -> None:
        self.proposal = proposal

    def __call__(self, **_kwargs: str) -> str:
        return json.dumps(self.proposal, ensure_ascii=False)


class TravelChatEvaluator:
    def __init__(
        self,
        *,
        runtime: RuntimeService | None = None,
        chat_handler: Callable[..., dict[str, Any]] = handle_travel_chat,
    ) -> None:
        self.runtime = runtime or RuntimeService()
        self.chat_handler = chat_handler

    def run(
        self,
        cases: Sequence[dict[str, Any]],
        *,
        mode: str = "mock",
    ) -> dict[str, Any]:
        if mode not in {"mock", "live"}:
            raise ChatEvalError("mode must be 'mock' or 'live'")

        trips_response = self._runtime_read("get_trips", {})
        trips = _extract_trips(trips_response)
        records = [self._run_case(case, trips=trips, mode=mode) for case in cases]
        skill_ids = sorted({record["skill_id"] for record in records})
        layer_summary = summarize_layers(records)
        improvement_opportunities = build_improvement_opportunities(
            layer_summary, total=len(records)
        )
        root_cause_summary = summarize_root_causes(records)
        root_cause_opportunities = build_root_cause_opportunities(
            root_cause_summary, total=len(records)
        )
        failures = [
            {
                "skill_id": record["skill_id"],
                "question": record["question"],
                "expected": record["expected"],
                "actual": record["actual"],
                "category": record["outcome_classification"],
                "failure_layer": record["failure_layer"],
                "failure_root_cause": record["failure_root_cause"],
                "improvement_hint": record["improvement_hint"],
                "trace": record["trace"],
            }
            for record in records
            if not record["passed"]
        ]
        summary = {
            "benchmark_version": BENCHMARK_VERSION,
            "skill_id": skill_ids[0] if len(skill_ids) == 1 else None,
            "skill_ids": skill_ids,
            "mode": mode,
            "total": len(records),
            "passed": len(records) - len(failures),
            "failed": len(failures),
            "failure_categories": {
                category: sum(
                    record["failure_category"] == category for record in records
                )
                for category in FAILURE_CATEGORIES
            },
            "failures": failures,
            "baseline": {
                "get_trips": _redact_value(trips_response),
                "trip_count": len(trips),
            },
            "records": records,
            "improvement_hints": _improvement_hints(records),
            "layer_summary": layer_summary,
            "improvement_opportunities": improvement_opportunities,
            "root_cause_summary": root_cause_summary,
            "root_cause_opportunities": root_cause_opportunities,
            # Keep the v0.1 field readable for existing report consumers.
            "top_improvements": improvement_opportunities,
        }
        summary["recommended_next_actions"] = build_recommended_next_actions(summary)
        summary["executive_summary"] = build_executive_summary(summary)
        return summary

    def _run_case(
        self,
        case: dict[str, Any],
        *,
        trips: list[dict[str, Any]],
        mode: str,
    ) -> dict[str, Any]:
        question = _required_string(case, "question")
        skill_id = case.get("skill_id", "travel")
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ChatEvalError("skill_id must be a non-empty string")
        skill_id = skill_id.strip().casefold()
        context, context_error, case_baseline = self._resolve_context(case, trips)
        generator = None
        if mode == "mock":
            proposal = case.get("mock_proposal")
            if not isinstance(proposal, dict):
                raise ChatEvalError(f"mock_proposal is required: {question}")
            generator = FixedProposalGenerator(proposal)

        if context_error is None:
            try:
                actual = self.chat_handler(
                    question,
                    role="admin",
                    debug=True,
                    context=context,
                    text_generator=generator,
                    runtime=self.runtime,
                )
            except Exception as exc:  # Keep one bad case from hiding the full eval.
                actual = {
                    "action": "runtime_error",
                    "reply": f"{exc.__class__.__name__}: {exc}",
                    "debug": {"steps": []},
                }
        else:
            actual = {
                "action": "needs_context",
                "reply": context_error,
                "updated_context": {},
                "debug": {"steps": []},
            }

        passed, classification = _compare(case, actual)
        failure_layer = None if passed else classify_failure_layer(classification)
        improvement_hint = (
            None if failure_layer is None else improvement_hint_for_layer(failure_layer)
        )
        expected = {
            key: value
            for key, value in case.items()
            if key not in {"mock_proposal", "id"}
        }
        trace = _build_trace(
            question=question,
            proposal=case.get("mock_proposal") if mode == "mock" else None,
            actual=actual,
            trips=trips,
            failure_category=None if passed else classification,
            failure_layer=failure_layer,
            improvement_hint=improvement_hint,
        )
        failure_root_cause = None
        if not passed:
            failure_root_cause = classify_failure_root_cause(
                question=question,
                expected=expected,
                actual=_compact_actual(actual),
                candidates=actual.get("candidates", []),
                trace=trace,
                failure_category=classification,
            )
        trace["failure_root_cause"] = failure_root_cause
        record = {
            "id": case.get("id"),
            "skill_id": skill_id,
            "question": question,
            "expected_intent": case.get("expected_intent"),
            "expected_entity": case.get("expected_entity"),
            "expected_trip": case.get("expected_trip_title"),
            "actual_action": actual.get("action"),
            "actual_tool_id": actual.get("tool_id"),
            "actual_arguments": actual.get("arguments", {}),
            "actual_reply": actual.get("reply", ""),
            "candidates": actual.get("candidates", []),
            "navigation": actual.get("navigation"),
            "updated_context": actual.get("updated_context", {}),
            "debug_steps": _debug_steps(actual),
            "baseline": _redact_value(case_baseline),
            "outcome_classification": classification,
            "failure_category": None if passed else classification,
            "failure_layer": failure_layer,
            "failure_root_cause": failure_root_cause,
            "improvement_hint": improvement_hint,
            "passed": passed,
            "expected": expected,
            "actual": _compact_actual(actual),
            "trace": trace,
        }
        return _redact_value(record)

    def _resolve_context(
        self,
        case: dict[str, Any],
        trips: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
        required_title = case.get("requires_context")
        if required_title is not None and (
            not isinstance(required_title, str) or not required_title.strip()
        ):
            raise ChatEvalError("requires_context must be a non-empty trip title")
        title = required_title or case.get("expected_trip_title")
        if not isinstance(title, str) or not title.strip():
            return None, None, {}
        trip = next((item for item in trips if item.get("title") == title), None)
        if trip is None or not isinstance(trip.get("id"), str):
            error = (
                f"基準Runtimeに文脈対象の旅行「{title}」がありません。"
                if required_title is not None
                else None
            )
            return None, error, {}

        trip_id = trip["id"]
        baseline = {
            "get_trip": self._runtime_read("get_trip", {"trip_id": trip_id})
        }
        if case.get("expected_tool") == "get_trip_timeline":
            baseline["get_trip_timeline"] = self._runtime_read(
                "get_trip_timeline", {"trip_id": trip_id}
            )
        context = None
        if required_title is not None:
            context = {
                "selected_trip_id": trip_id,
                "selected_trip_title": title,
            }
        return context, None, baseline

    def _runtime_read(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.runtime.execute_stub(
            tool_id,
            params=params,
            confirmed=False,
            role="admin",
        )
        if not isinstance(response, dict) or not response.get("success"):
            raise ChatEvalError(f"baseline Runtime read failed: {tool_id}")
        result = response.get("result")
        return result if isinstance(result, dict) else {}


def load_cases(path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChatEvalError(f"failed to load cases: {source}") from exc
    if not isinstance(payload, list) or not payload:
        raise ChatEvalError("case file must contain a non-empty JSON array")
    if not all(isinstance(case, dict) for case in payload):
        raise ChatEvalError("every case must be a JSON object")
    return payload


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Jarvis Benchmark Report",
        "",
        "## Executive Summary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary.get("executive_summary", []))
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Benchmark Version: `{summary['benchmark_version']}`",
        f"- Skill IDs: {', '.join(f'`{item}`' for item in summary['skill_ids'])}",
        f"- Mode: `{summary['mode']}`",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        "",
        "## Failure categories count",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ])
    lines.extend(
        f"| `{category}` | {count} |"
        for category, count in summary["failure_categories"].items()
    )
    lines.extend(["", "## Layer Summary", ""])
    for skill_id, layer_counts in summary["layer_summary"].items():
        lines.extend(
            [
                f"### {_skill_label(skill_id)} (`{skill_id}`)",
                "",
                "| Failure Layer | Count |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {_layer_label(layer)} | {count} |"
            for layer, count in layer_counts.items()
        )
        lines.append("")
    lines.extend(
        [
            "## Failure Analysis",
            "",
            "失敗ケースをLayerに加えてRoot Cause単位で分析します。",
            "",
            "## Root Cause Summary",
            "",
        ]
    )
    lines.extend(
        [
            "| Root Cause | Count | Representative Questions | Improvement | Expected | Difficulty |",
            "| --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for root_cause, item in summary.get("root_cause_summary", {}).items():
        questions = " / ".join(item["representative_questions"]) or "-"
        lines.append(
            f"| `{root_cause}` | {item['count']} | {_cell(questions)} | "
            f"{_cell(item['improvement_candidate'])} | "
            f"{item['expected_improvement_count']} | {item['difficulty']} |"
        )
    lines.extend(["", "## Top Root Causes", ""])
    root_opportunities = summary.get("root_cause_opportunities", [])
    if not root_opportunities:
        lines.append("失敗Root Causeはありません。")
    for index, item in enumerate(root_opportunities, start=1):
        lines.append(
            f"{index}. `{item['failure_root_cause']}`: {item['count']}件 / "
            f"改善案: {item['improvement_candidate']} / "
            f"想定改善: {item['expected_improvement_count']}件 / "
            f"難易度: {item['difficulty']}"
        )
    lines.extend([
        "## Case table",
        "",
        "| Result | Skill | Question | Expected | Actual | Classification | Layer | Root Cause |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for record in summary["records"]:
        expected = record.get("expected_trip") or record["expected"].get(
            "expected_tool", record["expected"].get("expected_outcome", "-")
        )
        actual = record.get("actual_tool_id") or record.get("actual_action") or "-"
        result = "PASS" if record["passed"] else "FAIL"
        lines.append(
            f"| {result} | `{record['skill_id']}` | {_cell(record['question'])} | "
            f"{_cell(expected)} | {_cell(actual)} | "
            f"{_cell(record['outcome_classification'])} | "
            f"{_cell(record['failure_layer'] or '-')} | "
            f"{_cell(record.get('failure_root_cause') or '-')} |"
        )
    lines.extend(["", "## Failure Details", ""])
    failures = [record for record in summary["records"] if not record["passed"]]
    if not failures:
        lines.append("失敗ケースはありません。")
    for record in failures:
        lines.extend(
            [
                f"### {_cell(record['id'] or record['question'])}",
                "",
                f"- Skill ID: `{record['skill_id']}`",
                f"- Category: `{record['failure_category']}`",
                f"- Failure Layer: `{record['failure_layer']}`",
                f"- Failure Root Cause: `{record.get('failure_root_cause') or 'unknown'}`",
                f"- Improvement Hint: {record['improvement_hint']}",
                f"- Expected: `{_cell(record['expected'])}`",
                f"- Actual: `{_cell(record['actual'])}`",
                "",
            ]
        )
    lines.extend(["", "## Reason Trace", ""])
    for record in summary["records"]:
        lines.extend(
            [
                f"### {_cell(record['id'] or record['question'])}",
                "",
                "```json",
                json.dumps(record["trace"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(["## 改善ヒント", ""])
    lines.extend(f"- {hint}" for hint in summary["improvement_hints"])
    lines.extend(["", "## Improvement Opportunities", ""])
    opportunities = summary.get(
        "improvement_opportunities", summary.get("top_improvements", [])
    )
    if not opportunities:
        lines.append("失敗レイヤーはありません。")
    for index, target in enumerate(opportunities, start=1):
        lines.extend(
            [
                f"### {index}. {_skill_label(target['skill_id'])} / "
                f"{_layer_label(target['failure_layer'])}",
                "",
                f"- Failure Layer: `{target['failure_layer']}`",
                f"- 件数: {target['count']}",
                f"- 全体割合: {target['percentage']:.1f}%",
                f"- 改善候補: {target['improvement_candidate']}",
                f"- 期待効果: {target['expected_effect']}",
                f"- 推奨優先度: **{target['priority']}**",
                "",
            ]
        )
    lines.extend(["## Root Cause Opportunities", ""])
    if not root_opportunities:
        lines.append("失敗Root Causeはありません。")
    for index, target in enumerate(root_opportunities, start=1):
        lines.extend(
            [
                f"### {index}. `{target['failure_root_cause']}`",
                "",
                f"- 件数: {target['count']}",
                f"- 全体割合: {target['percentage']:.1f}%",
                f"- 改善候補: {target['improvement_candidate']}",
                f"- 想定改善件数: {target['expected_improvement_count']}",
                f"- 実装難易度: **{target['difficulty']}**",
                "",
            ]
        )
    lines.extend(["## Recommended Next Actions", ""])
    actions = summary.get("recommended_next_actions", [])
    if not actions:
        lines.append("追加アクションはありません。")
    for action in actions:
        lines.append(
            f"{action['rank']}. `{action['failure_root_cause']}` — "
            f"{action['action']}（想定改善: {action['expected_improvement_count']}件、"
            f"難易度: {action['difficulty']}）"
        )
    return redact_sensitive_text("\n".join(lines) + "\n")


def write_reports(
    summary: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_target.write_text(render_markdown(summary), encoding="utf-8")


def save_baseline(summary: dict[str, Any], path: str | Path = "baseline.json") -> None:
    """Persist a complete benchmark result for later comparison."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_redact_value(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_benchmark(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChatEvalError(f"failed to load benchmark: {source}") from exc
    if not isinstance(payload, dict):
        raise ChatEvalError("benchmark file must contain a JSON object")
    if not isinstance(payload.get("total"), int) or not isinstance(
        payload.get("passed"), int
    ):
        raise ChatEvalError("benchmark file is missing total or passed")
    if not isinstance(payload.get("layer_summary"), dict):
        raise ChatEvalError("benchmark file is missing layer_summary")
    return payload


def _compare(
    case: dict[str, Any], actual: dict[str, Any]
) -> tuple[bool, str]:
    action = actual.get("action")
    tool_id = actual.get("tool_id")
    if _contains_unredacted_secret(actual):
        return False, "security_violation"
    if action == "runtime_error":
        return False, "runtime_error"
    reply = actual.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        return False, "response_not_human_friendly"
    expected_classification = case.get("expected_classification")
    if expected_classification == "unsupported_or_needs_experience_context":
        passed = action == "needs_context"
        return passed, "pass" if passed else "unsupported_expected"

    expected_outcome = case.get("expected_outcome")
    if expected_outcome == "candidates":
        candidates = actual.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return False, "entity_resolution_missing"
        expected_titles = set(case.get("expected_contains_titles", []))
        actual_titles = {
            item.get("title") for item in candidates if isinstance(item, dict)
        }
        passed = expected_titles.issubset(actual_titles)
        return passed, "pass" if passed else "wrong_entity"
    if expected_outcome in {"not_found", "not_found_or_needs_context"}:
        passed = action == "needs_context" and not actual.get("candidates")
        return passed, "pass" if passed else "wrong_entity"

    expected_title = case.get("expected_trip_title")
    if expected_title:
        actual_title = _actual_trip_title(actual)
        if actual_title != expected_title:
            if case.get("allow_candidate_if_ambiguous") and _candidate_has_title(
                actual, expected_title
            ):
                return True, "pass"
            if case.get("requires_context"):
                return False, "context_not_used"
            if actual.get("candidates"):
                return False, "entity_resolution_ambiguous"
            return False, "entity_resolution_missing"

    expected_tool = case.get("expected_tool")
    if expected_tool and tool_id != expected_tool:
        if case.get("requires_context"):
            return False, "context_not_used"
        return False, "tool_selection_error"

    if expected_tool and action != "tool_result":
        return False, "runtime_error"
    expected_reply_contains = case.get("expected_reply_contains")
    if (
        isinstance(expected_reply_contains, str)
        and expected_reply_contains not in reply
    ):
        return False, "response_not_human_friendly"
    return True, "pass"


def _build_trace(
    *,
    question: str,
    proposal: Any,
    actual: dict[str, Any],
    trips: list[dict[str, Any]],
    failure_category: str | None,
    failure_layer: str | None,
    improvement_hint: str | None,
) -> dict[str, Any]:
    proposal = proposal if isinstance(proposal, dict) else {}
    search_candidates = _trace_search_candidates(question, trips)
    visible_candidates = actual.get("candidates")
    decision = _trace_decision(actual, search_candidates)
    debug = actual.get("debug")
    resolution = (
        debug.get("entity_resolution") if isinstance(debug, dict) else None
    )
    resolution = resolution if isinstance(resolution, dict) else {}
    return _redact_value(
        {
            "question": question,
            "planner": {
                "proposed_tool": proposal.get("tool_id") or actual.get("tool_id"),
                "proposed_arguments": proposal.get("arguments", {}),
                "confidence": proposal.get("confidence"),
            },
            "runtime_steps": _trace_runtime_steps(actual, trips),
            "search_candidates": search_candidates,
            "resolver": resolution.get("resolver"),
            "resolution_status": resolution.get("resolution_status"),
            "candidate_count": resolution.get("candidate_count"),
            "top_candidate_score": resolution.get("top_candidate_score"),
            "decision": decision,
            "clarification_layer": _trace_clarification(actual),
            "response_summary": {
                "action": actual.get("action"),
                "outcome": (
                    "candidates"
                    if isinstance(visible_candidates, list) and visible_candidates
                    else actual.get("action")
                ),
                "reply": actual.get("reply", ""),
                "candidate_count": (
                    len(visible_candidates)
                    if isinstance(visible_candidates, list)
                    else 0
                ),
            },
            "failure_category": failure_category,
            "failure_layer": failure_layer,
            "improvement_hint": improvement_hint,
        }
    )


def _trace_search_candidates(
    question: str, trips: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    trips_by_id = {
        trip.get("id"): trip
        for trip in trips
        if isinstance(trip.get("id"), str)
    }
    candidates = TravelSearchIndex().search(question, trips)
    return [
        {
            "id": candidate.entity.entity_id,
            "title": candidate.entity.label,
            "score": candidate.score,
            "matched_by": [
                item for item in candidate.matched_by.split(",") if item
            ],
            "prefectures": trips_by_id.get(candidate.entity.entity_id, {}).get(
                "prefectures"
            ),
        }
        for candidate in candidates
    ]


def _trace_runtime_steps(
    actual: dict[str, Any], trips: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    steps = []
    debug_steps = _debug_steps(actual)
    for index, raw_step in enumerate(debug_steps):
        if not isinstance(raw_step, dict):
            continue
        step = dict(raw_step)
        tool_id = step.get("tool_id")
        if tool_id == "get_trips":
            step["result_summary"] = f"trips={len(trips)}"
        elif index == len(debug_steps) - 1:
            step["result_summary"] = _result_summary(actual.get("result"))
        steps.append(step)
    return steps


def _result_summary(result: Any) -> str:
    if not isinstance(result, dict):
        return "result=none"
    trip = result.get("trip")
    if isinstance(trip, dict):
        return f"trip={trip.get('title') or trip.get('id') or 'unknown'}"
    timeline = result.get("timeline")
    if isinstance(timeline, list):
        return f"timeline_items={len(timeline)}"
    trips = result.get("trips")
    if isinstance(trips, list):
        return f"trips={len(trips)}"
    return "result=available"


def _trace_decision(
    actual: dict[str, Any], search_candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    visible = actual.get("candidates")
    if isinstance(visible, list) and visible:
        clarification = actual.get("clarification")
        reason = (
            clarification.get("reason")
            if isinstance(clarification, dict)
            else None
        )
        return {"type": "ambiguous", "reason": reason or "multiple_candidates"}
    if actual.get("action") == "tool_result":
        return {"type": "resolved", "reason": "single_candidate_or_direct_tool"}
    if actual.get("action") == "runtime_error":
        return {"type": "error", "reason": "runtime_error"}
    if actual.get("action") == "needs_context":
        return {
            "type": "not_found" if not search_candidates else "needs_context",
            "reason": (
                "no_search_candidates"
                if not search_candidates
                else "additional_context_required"
            ),
        }
    return {"type": "unsupported", "reason": "no_runtime_decision"}


def _trace_clarification(actual: dict[str, Any]) -> dict[str, Any] | None:
    clarification = actual.get("clarification")
    if not isinstance(clarification, dict):
        return None
    candidates = clarification.get("candidate_list")
    return {
        "status": clarification.get("status"),
        "reason": clarification.get("reason"),
        "recommended_action": clarification.get("recommended_action"),
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
    }


def classify_failure_layer(failure_category: str) -> str:
    """Map one failure category to one actionable benchmark layer."""
    return _FAILURE_CATEGORY_LAYERS.get(failure_category, "unknown")


def improvement_hint_for_layer(failure_layer: str) -> str:
    """Return a stable, implementation-oriented hint for a benchmark layer."""
    return _IMPROVEMENT_HINTS.get(failure_layer, _IMPROVEMENT_HINTS["unknown"])


def classify_failure_root_cause(
    *,
    question: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    candidates: Any,
    trace: dict[str, Any],
    failure_category: str,
) -> str:
    """Classify a failed case from its expectation and observable Reason Trace."""
    expected_classification = expected.get("expected_classification")
    decision = trace.get("decision")
    decision_type = decision.get("type") if isinstance(decision, dict) else None
    actual_action = actual.get("action")
    search_candidates = trace.get("search_candidates")
    has_search_candidates = isinstance(search_candidates, list) and bool(
        search_candidates
    )
    has_visible_candidates = isinstance(candidates, list) and bool(candidates)

    if failure_category == "context_not_used":
        return "context_slot_missing"
    if expected_classification == "memo_derived" and not has_search_candidates:
        return "missing_memo_paraphrase"
    if expected_classification == "ambiguous_query":
        return "query_too_broad"
    if expected_classification == "unsupported_or_needs_experience_context":
        return (
            "missing_experience_search"
            if "体験" in question or "経験" in question
            else "unsupported_intent"
        )
    if (
        expected.get("expected_outcome") == "candidates"
        and decision_type == "resolved"
        and actual_action == "tool_result"
        and not has_visible_candidates
    ):
        return "ambiguous_expected_but_resolved"
    if failure_category == "unsupported_expected":
        return "unsupported_intent"
    if failure_category in {"entity_resolution_missing", "wrong_entity"}:
        return "missing_semantic_match"
    if failure_category == "entity_resolution_ambiguous" and has_visible_candidates:
        return "benchmark_expectation_mismatch"
    return "unknown"


def summarize_root_causes(
    records: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarize counts, examples, impact, and implementation difficulty."""
    summary = {
        root_cause: {
            "count": 0,
            "representative_questions": [],
            "improvement_candidate": guidance["improvement_candidate"],
            "expected_improvement_count": 0,
            "difficulty": guidance["difficulty"],
        }
        for root_cause, guidance in _ROOT_CAUSE_GUIDANCE.items()
    }
    for record in records:
        root_cause = record.get("failure_root_cause")
        if root_cause is None:
            continue
        normalized = root_cause if root_cause in FAILURE_ROOT_CAUSES else "unknown"
        item = summary[normalized]
        item["count"] += 1
        question = record.get("question")
        if (
            isinstance(question, str)
            and question
            and len(item["representative_questions"]) < 3
        ):
            item["representative_questions"].append(question)
    for item in summary.values():
        item["expected_improvement_count"] = item["count"]
    return summary


def build_root_cause_opportunities(
    root_cause_summary: dict[str, dict[str, Any]], *, total: int
) -> list[dict[str, Any]]:
    """Rank root causes without changing legacy layer-based opportunities."""
    root_order = {
        root_cause: index for index, root_cause in enumerate(FAILURE_ROOT_CAUSES)
    }
    opportunities = []
    for root_cause, summary in root_cause_summary.items():
        count = summary.get("count", 0)
        if not isinstance(count, int) or count <= 0:
            continue
        percentage = (count / total * 100.0) if total else 0.0
        opportunities.append(
            {
                "failure_root_cause": root_cause,
                "count": count,
                "percentage": round(percentage, 1),
                "representative_questions": list(
                    summary.get("representative_questions", [])
                ),
                "improvement_candidate": summary["improvement_candidate"],
                "expected_improvement_count": summary[
                    "expected_improvement_count"
                ],
                "difficulty": summary["difficulty"],
                "priority": priority_for_percentage(percentage),
            }
        )
    return sorted(
        opportunities,
        key=lambda item: (
            -item["count"],
            root_order.get(item["failure_root_cause"], len(FAILURE_ROOT_CAUSES)),
        ),
    )


def build_recommended_next_actions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn ranked root-cause opportunities into deterministic next actions."""
    return [
        {
            "rank": index,
            "failure_root_cause": opportunity["failure_root_cause"],
            "action": opportunity["improvement_candidate"],
            "expected_improvement_count": opportunity[
                "expected_improvement_count"
            ],
            "difficulty": opportunity["difficulty"],
        }
        for index, opportunity in enumerate(
            summary.get("root_cause_opportunities", []), start=1
        )
    ]


def summarize_layers(
    records: Sequence[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count failed records by skill and layer, retaining zero-value layers."""
    skill_ids = sorted(
        {
            str(record.get("skill_id", "unknown"))
            for record in records
            if record.get("skill_id")
        }
    )
    summary = {
        skill_id: {layer: 0 for layer in FAILURE_LAYERS}
        for skill_id in skill_ids
    }
    for record in records:
        layer = record.get("failure_layer")
        if layer is None:
            continue
        skill_id = str(record.get("skill_id") or "unknown")
        if skill_id not in summary:
            summary[skill_id] = {item: 0 for item in FAILURE_LAYERS}
        normalized_layer = layer if layer in FAILURE_LAYERS else "unknown"
        summary[skill_id][normalized_layer] += 1
    return summary


def rank_top_improvements(
    layer_summary: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """Rank skill/layer improvement targets by failed-case count."""
    layer_order = {layer: index for index, layer in enumerate(FAILURE_LAYERS)}
    targets = [
        {
            "skill_id": skill_id,
            "failure_layer": layer,
            "count": count,
            "improvement_hint": improvement_hint_for_layer(layer),
        }
        for skill_id, counts in layer_summary.items()
        for layer, count in counts.items()
        if count > 0
    ]
    return sorted(
        targets,
        key=lambda item: (
            -item["count"],
            item["skill_id"],
            layer_order.get(item["failure_layer"], len(FAILURE_LAYERS)),
        ),
    )


def build_improvement_opportunities(
    layer_summary: dict[str, dict[str, int]], *, total: int
) -> list[dict[str, Any]]:
    """Describe ranked improvements with impact and a stable priority rule."""
    opportunities = []
    for target in rank_top_improvements(layer_summary):
        percentage = (target["count"] / total * 100.0) if total else 0.0
        opportunities.append(
            {
                **target,
                "percentage": round(percentage, 1),
                "improvement_candidate": target["improvement_hint"],
                "expected_effect": _EXPECTED_EFFECTS.get(
                    target["failure_layer"], _EXPECTED_EFFECTS["unknown"]
                ),
                "priority": priority_for_percentage(percentage),
            }
        )
    return opportunities


def priority_for_percentage(percentage: float) -> str:
    """Map total-case impact to a recommendation priority."""
    if percentage >= 20.0:
        return "High"
    if percentage >= 10.0:
        return "Medium"
    return "Low"


def build_executive_summary(summary: dict[str, Any]) -> list[str]:
    """Create deterministic, human-readable findings from one benchmark result."""
    opportunities = summary.get("improvement_opportunities", [])
    findings: list[str] = []
    if opportunities:
        top = opportunities[0]
        findings.append(
            f"{_layer_label(top['failure_layer'])}が全ケースの"
            f"{top['percentage']:.1f}%（{top['count']}件）を占めています。"
        )
    else:
        findings.append("固定ケースで失敗は検出されていません。")

    aggregate = _aggregate_layers(summary.get("layer_summary", {}))
    for layer in ("context", "planner"):
        count = aggregate[layer]
        if count == 0:
            findings.append(f"{_layer_label(layer)}は失敗0件で安定しています。")
        elif count == 1:
            findings.append(f"{_layer_label(layer)}の残課題は1件です。")
    if opportunities:
        top = opportunities[0]
        findings.append(
            f"次は{top['improvement_candidate'].rstrip('。')}ことが最も効果的です。"
        )
    return findings


def compare_benchmarks(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    """Compare results; positive layer deltas mean fewer failures."""
    baseline_layers = _aggregate_layers(baseline.get("layer_summary", {}))
    current_layers = _aggregate_layers(current.get("layer_summary", {}))
    layers = {
        layer: {
            "baseline": baseline_layers[layer],
            "current": current_layers[layer],
            "delta": baseline_layers[layer] - current_layers[layer],
        }
        for layer in FAILURE_LAYERS
    }
    baseline_rate = _pass_rate(baseline)
    current_rate = _pass_rate(current)
    regressions = detect_regressions(layers)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "baseline_version": baseline.get("benchmark_version"),
        "current_version": current.get("benchmark_version"),
        "layers": layers,
        "overall": {
            "baseline_pass_rate": baseline_rate,
            "current_pass_rate": current_rate,
            "delta_percentage_points": round(current_rate - baseline_rate, 1),
        },
        "regressions": regressions,
        "has_regression": bool(regressions),
    }


def detect_regressions(
    layer_diff: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """Return layers whose failure count increased from the baseline."""
    return [
        {
            "failure_layer": layer,
            "baseline": values["baseline"],
            "current": values["current"],
            "increase": -values["delta"],
        }
        for layer, values in layer_diff.items()
        if values["delta"] < 0
    ]


def render_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Jarvis Benchmark Diff",
        "",
        "正の差分は改善、負の差分は悪化を表します。",
        "",
        "## Layer Diff",
        "",
        "| Layer | Baseline Failures | Current Failures | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for layer, values in diff["layers"].items():
        lines.append(
            f"| {_layer_label(layer)} | {values['baseline']} | "
            f"{values['current']} | {values['delta']:+d} |"
        )
    overall = diff["overall"]
    lines.extend(
        [
            "",
            "## Overall",
            "",
            f"- Pass rate: {overall['baseline_pass_rate']:.1f}% → "
            f"{overall['current_pass_rate']:.1f}% "
            f"({overall['delta_percentage_points']:+.1f} points)",
            "",
            "## Regression Detection",
            "",
        ]
    )
    if not diff["regressions"]:
        lines.append("Regressionは検出されませんでした。")
    else:
        for regression in diff["regressions"]:
            lines.append(
                f"- **Regression**: {_layer_label(regression['failure_layer'])} "
                f"の失敗が{regression['increase']}件増加 "
                f"({regression['baseline']} → {regression['current']})"
            )
    return redact_sensitive_text("\n".join(lines) + "\n")


def _aggregate_layers(layer_summary: Any) -> dict[str, int]:
    aggregate = {layer: 0 for layer in FAILURE_LAYERS}
    if not isinstance(layer_summary, dict):
        return aggregate
    for counts in layer_summary.values():
        if not isinstance(counts, dict):
            continue
        for layer, count in counts.items():
            normalized = layer if layer in FAILURE_LAYERS else "unknown"
            if isinstance(count, int) and count >= 0:
                aggregate[normalized] += count
    return aggregate


def _pass_rate(summary: dict[str, Any]) -> float:
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    if not isinstance(total, int) or total <= 0 or not isinstance(passed, int):
        return 0.0
    return round(passed / total * 100.0, 1)


def _improvement_hints(records: Sequence[dict[str, Any]]) -> list[str]:
    targets = rank_top_improvements(summarize_layers(records))
    hints = [
        f"{target['skill_id']} / {target['failure_layer']} "
        f"({target['count']}件): {target['improvement_hint']}"
        for target in targets
    ]
    return hints or ["失敗レイヤーはありません。現状の固定ケースを回帰基準として維持する。"]


def _contains_unredacted_secret(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return "bearer " in lowered or "sk-" in lowered
    if isinstance(value, dict):
        return any(
            _is_sensitive_key(str(key)) or _contains_unredacted_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_unredacted_secret(item) for item in value)
    return False


def _actual_trip_title(actual: dict[str, Any]) -> str | None:
    result = actual.get("result")
    if isinstance(result, dict):
        trip = result.get("trip")
        if isinstance(trip, dict) and isinstance(trip.get("title"), str):
            return trip["title"]
    return None


def _candidate_has_title(actual: dict[str, Any], title: str) -> bool:
    candidates = actual.get("candidates")
    return isinstance(candidates, list) and any(
        isinstance(item, dict) and item.get("title") == title for item in candidates
    )


def _extract_trips(result: dict[str, Any]) -> list[dict[str, Any]]:
    trips = result.get("trips")
    if not isinstance(trips, list):
        return []
    return [trip for trip in trips if isinstance(trip, dict)]


def _debug_steps(actual: dict[str, Any]) -> list[dict[str, Any]]:
    debug = actual.get("debug")
    steps = debug.get("steps") if isinstance(debug, dict) else None
    return steps if isinstance(steps, list) else []


def _compact_actual(actual: dict[str, Any]) -> dict[str, Any]:
    return {
        key: actual.get(key)
        for key in (
            "action",
            "tool_id",
            "arguments",
            "reply",
            "candidates",
            "navigation",
            "updated_context",
        )
        if actual.get(key) is not None
    }


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ChatEvalError(f"{key} must be a non-empty string")
    return item.strip()


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _skill_label(skill_id: str) -> str:
    return skill_id.replace("_", " ").title()


def _layer_label(layer: str) -> str:
    return layer.replace("_", " ").title()


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(str(key)) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return normalized in {
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Travel Chat conversations")
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("BASELINE", "CURRENT"),
        help="Compare two benchmark JSON files instead of running cases",
    )
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--json-output", default="artifacts/chat_eval_summary.json")
    parser.add_argument("--markdown-output", default="artifacts/chat_eval_report.md")
    parser.add_argument("--format", choices=("json", "markdown"))
    parser.add_argument(
        "--save-baseline",
        nargs="?",
        const="baseline.json",
        metavar="PATH",
        help="Save the benchmark result (default: baseline.json)",
    )
    parser.add_argument(
        "--output",
        help="Write the selected --format to this path (requires --format)",
    )
    args = parser.parse_args(argv)
    if args.output and not args.format:
        parser.error("--output requires --format")

    if args.diff:
        diff = compare_benchmarks(
            load_benchmark(args.diff[0]), load_benchmark(args.diff[1])
        )
        rendered = (
            json.dumps(diff, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_diff_markdown(diff)
        )
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 1 if diff["has_regression"] else 0

    summary = TravelChatEvaluator().run(load_cases(args.cases), mode=args.mode)
    if args.save_baseline:
        save_baseline(summary, args.save_baseline)
    if args.format:
        rendered = (
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(summary)
        )
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    else:
        write_reports(
            summary,
            json_path=args.json_output,
            markdown_path=args.markdown_output,
        )
        print(
            json.dumps(
                {key: summary[key] for key in ("total", "passed", "failed")},
                ensure_ascii=False,
            )
        )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
