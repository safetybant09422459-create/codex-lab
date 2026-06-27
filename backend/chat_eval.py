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
        failures = [
            {
                "question": record["question"],
                "expected": record["expected"],
                "actual": record["actual"],
                "category": record["outcome_classification"],
                "trace": record["trace"],
            }
            for record in records
            if not record["passed"]
        ]
        return {
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
        }

    def _run_case(
        self,
        case: dict[str, Any],
        *,
        trips: list[dict[str, Any]],
        mode: str,
    ) -> dict[str, Any]:
        question = _required_string(case, "question")
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
        )
        record = {
            "id": case.get("id"),
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
        "# Travel Chat Eval Report",
        "",
        "## Summary",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        "",
        "## Failure categories count",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| `{category}` | {count} |"
        for category, count in summary["failure_categories"].items()
    )
    lines.extend([
        "",
        "## Case table",
        "",
        "| Result | Question | Expected | Actual | Classification |",
        "| --- | --- | --- | --- | --- |",
    ])
    for record in summary["records"]:
        expected = record.get("expected_trip") or record["expected"].get(
            "expected_tool", record["expected"].get("expected_outcome", "-")
        )
        actual = record.get("actual_tool_id") or record.get("actual_action") or "-"
        result = "PASS" if record["passed"] else "FAIL"
        lines.append(
            f"| {result} | {_cell(record['question'])} | {_cell(expected)} | "
            f"{_cell(actual)} | {_cell(record['outcome_classification'])} |"
        )
    lines.extend(["", "## Failure detail", ""])
    failures = [record for record in summary["records"] if not record["passed"]]
    if not failures:
        lines.append("失敗ケースはありません。")
    for record in failures:
        lines.extend(
            [
                f"### {_cell(record['id'] or record['question'])}",
                "",
                f"- Category: `{record['failure_category']}`",
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
    return True, "pass"


def _build_trace(
    *,
    question: str,
    proposal: Any,
    actual: dict[str, Any],
    trips: list[dict[str, Any]],
    failure_category: str | None,
) -> dict[str, Any]:
    proposal = proposal if isinstance(proposal, dict) else {}
    search_candidates = _trace_search_candidates(question, trips)
    visible_candidates = actual.get("candidates")
    decision = _trace_decision(actual, search_candidates)
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
            "decision": decision,
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
        return {"type": "ambiguous", "reason": "multiple_candidates"}
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


def _improvement_hints(records: Sequence[dict[str, Any]]) -> list[str]:
    counts = {
        category: sum(record.get("failure_category") == category for record in records)
        for category in FAILURE_CATEGORIES
    }
    rules = {
        "tool_selection_error": "PlannerのTool選択ルールとfew-shot例を見直す。",
        "entity_resolution_missing": "Search Indexの検索対象、query expansion、scoreを改善する。",
        "entity_resolution_ambiguous": "score差の閾値と候補提示フローを改善する。",
        "wrong_entity": "候補rankingとentity検証を改善する。",
        "context_not_used": "ConversationState / ContextReducerの文脈適用を改善する。",
        "response_not_human_friendly": "軽量なResponse Composerと返答テンプレートを改善する。",
        "unsupported_expected": "未対応intentの境界とneeds_context応答を明確化する。",
        "runtime_error": "Runtime stepとTool引数を確認し、失敗処理を改善する。",
        "security_violation": "trace出力のredactionと機密情報境界を最優先で修正する。",
    }
    hints = [f"{category} ({counts[category]}件): {rules[category]}" for category in FAILURE_CATEGORIES if counts[category]]
    return hints or ["失敗カテゴリはありません。現状の固定ケースを回帰基準として維持する。"]


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
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--json-output", default="artifacts/chat_eval_summary.json")
    parser.add_argument("--markdown-output", default="artifacts/chat_eval_report.md")
    parser.add_argument("--format", choices=("json", "markdown"))
    parser.add_argument(
        "--output",
        help="Write the selected --format to this path (requires --format)",
    )
    args = parser.parse_args(argv)
    if args.output and not args.format:
        parser.error("--output requires --format")

    summary = TravelChatEvaluator().run(load_cases(args.cases), mode=args.mode)
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
