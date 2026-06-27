from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from time import perf_counter
from typing import Any
from urllib.parse import quote

from .chat_tool_policy import (
    CHAT_TOOL_ARGUMENTS,
    CHAT_TRAVEL_TOOL_ALLOWLIST,
    get_chat_tool_execution_policy,
    validate_chat_proposal,
)
from .openai_adapter import (
    OpenAIRequestError,
    generate_text_with_timings,
    redact_sensitive_text,
)
from .runtime import RuntimeService


_FALLBACK = {
    "action": "needs_context",
    "reply": "Toolを安全に提案できませんでした。対象の旅行または体験をもう少し具体的に指定してください。",
}

_RUNTIME_ERROR_REPLY = "Toolの実行に失敗しました。時間をおいて再度お試しください。"
_PERMISSION_DENIED_REPLY = "この操作を実行する権限がありません。"
_WRITE_NOT_IMPLEMENTED_REPLY = "更新操作には確認が必要です。現在は提案のみ対応しています。"
_TRIP_NOT_FOUND_REPLY = "該当する旅行が見つかりませんでした。"
_MULTIPLE_TRIPS_REPLY = "候補が複数あります。"
_MAX_STEPS_REPLY = "安全のため処理を中断しました。対象の旅行をもう少し具体的に指定してください。"

MAX_TRAVEL_STEPS = 3

_SUCCESS_REPLIES = {
    "get_trips": "旅行一覧を取得しました。",
    "get_trip": "旅行情報を取得しました。",
    "get_trip_timeline": "旅行タイムラインを取得しました。",
    "get_experience": "体験情報を取得しました。",
    "get_experience_photos": "体験写真を取得しました。",
    "get_experience_photo_links": "体験写真リンクを取得しました。",
    "get_experience_photo_search": "体験写真の検索結果を取得しました。",
}

# Reused within the process. Runtime remains the only path to executors/repositories.
runtime_service = RuntimeService()

_INSTRUCTIONS = """\
You are the proposal-only Chat Orchestrator for Jarvis Travel Chat v0.1.
Return exactly one JSON object and no Markdown or commentary.
You propose a tool; you never execute it.

Allowed actions:
- tool_proposal: action, tool_id, arguments, confidence, reply
- needs_context: action, reply

Allowed tool IDs and arguments:
{tool_policy}

Rules:
- Never invent or decide role, confirmed, user_id, permission, or authorization.
- Server-owned conversation context may be included with the utterance. Use its
  selected_trip_id for references to the selected trip, but never return or update
  context yourself.
- Use only an allowed tool and only its listed arguments.
- A trip name is not a trip_id. To find a named trip, propose get_trips with empty arguments.
- A place or experience name is not an experience_id. If photos or details need an
  experience_id and no actual ID is available, return needs_context.
- update_experience is proposal-only and accepts exactly experience_id and memo.
- Do not request or return photo binary data.
- confidence must be high, medium, or low.
- reply must be concise Japanese suitable for the user.

Examples:
User: 旅行一覧を見せて
{{"action":"tool_proposal","tool_id":"get_trips","arguments":{{}},"confidence":"high","reply":"旅行一覧を取得します。"}}
User: 福岡旅行を開いて
{{"action":"tool_proposal","tool_id":"get_trips","arguments":{{}},"confidence":"medium","reply":"福岡旅行を探します。"}}
Context: selected_trip_id=trip_fukuoka, selected_trip_title=福岡旅行
User: この旅行の詳細見せて
{{"action":"tool_proposal","tool_id":"get_trip","arguments":{{"trip_id":"trip_fukuoka"}},"confidence":"high","reply":"選択中の旅行を取得します。"}}
Context: selected_trip_id=trip_fukuoka, selected_trip_title=福岡旅行
User: 2日目は？
{{"action":"tool_proposal","tool_id":"get_trip_timeline","arguments":{{"trip_id":"trip_fukuoka"}},"confidence":"high","reply":"選択中の旅行の日程を取得します。"}}
User: アンパンマンミュージアムの写真見せて
{{"action":"needs_context","reply":"どの旅行の体験か確認するため、旅行または体験を先に選んでください。"}}
""".format(
    tool_policy=json.dumps(
        {
            tool_id: sorted(CHAT_TOOL_ARGUMENTS[tool_id])
            for tool_id in sorted(CHAT_TRAVEL_TOOL_ALLOWLIST)
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
)


def propose_travel_tool(
    user_message: str,
    *,
    context: dict[str, Any] | None = None,
    text_generator: Callable[..., str] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Return a validated Travel Tool proposal without executing Runtime or a Tool."""
    total_started = perf_counter()
    timings_ms = {
        "build_prompt": 0.0,
        "llm_call": 0.0,
        "json_parse": 0.0,
        "policy_validation": 0.0,
        "fallback": 0.0,
        "total": 0.0,
    }
    adapter_timings_ms: dict[str, float] | None = None

    try:
        prompt_started = perf_counter()
        try:
            if not isinstance(user_message, str) or not user_message.strip():
                raise ValueError("user message must be a non-empty string")
            safe_message = redact_sensitive_text(user_message.strip())
            safe_context = _redact_value(_sanitize_context(context))
            context_text = json.dumps(
                safe_context,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            input_text = (
                "Server-normalized conversation context candidate (read-only):\n"
                f"{context_text}\n"
                f"User utterance:\n{safe_message}"
            )
        finally:
            timings_ms["build_prompt"] = _elapsed_ms(prompt_started)

        llm_started = perf_counter()
        try:
            if text_generator is None:
                raw_response, adapter_timings_ms = generate_text_with_timings(
                    instructions=_INSTRUCTIONS,
                    input_text=input_text,
                )
            else:
                raw_response = text_generator(
                    instructions=_INSTRUCTIONS,
                    input_text=input_text,
                )
        finally:
            timings_ms["llm_call"] = _elapsed_ms(llm_started)

        parse_started = perf_counter()
        try:
            parsed = json.loads(raw_response)
        finally:
            timings_ms["json_parse"] = _elapsed_ms(parse_started)

        validation_started = perf_counter()
        try:
            proposal = validate_chat_proposal(parsed)
        finally:
            timings_ms["policy_validation"] = _elapsed_ms(validation_started)

        result = _redact_proposal(proposal)
    except Exception as exc:
        if isinstance(exc, OpenAIRequestError) and exc.timings_ms is not None:
            adapter_timings_ms = exc.timings_ms
        # No raw model output or exception detail is returned or audited here.
        fallback_started = perf_counter()
        try:
            result = dict(_FALLBACK)
        finally:
            timings_ms["fallback"] = _elapsed_ms(fallback_started)

    timings_ms["total"] = _elapsed_ms(total_started)
    if debug:
        result["debug"] = {"timings_ms": timings_ms}
        if adapter_timings_ms is not None:
            result["debug"]["openai_adapter"] = {
                "timings_ms": adapter_timings_ms
            }
    return result


def handle_travel_chat(
    message: str,
    role: str = "admin",
    debug: bool = False,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a bounded server-side Travel read plan proposed by the LLM."""
    total_started = perf_counter()
    proposal_started = perf_counter()
    context_was_provided = context is not None
    updated_context = _sanitize_context(context)
    proposal = propose_travel_tool(
        message,
        context=updated_context,
        debug=debug,
    )
    proposal_total = _elapsed_ms(proposal_started)

    proposal_debug = proposal.pop("debug", None)
    runtime_steps: list[dict[str, Any]] = []

    if proposal.get("action") != "tool_proposal":
        result = proposal
    else:
        proposal, used_selected_trip = _apply_selected_trip_context(
            message,
            proposal,
            updated_context,
        )
        tool_id = proposal["tool_id"]
        arguments = proposal["arguments"]
        execution_policy = get_chat_tool_execution_policy(tool_id)

        if execution_policy == "write_requires_pending_action":
            result = {
                "action": "pending_write_not_implemented",
                "tool_id": tool_id,
                "arguments": arguments,
                "reply": _WRITE_NOT_IMPLEMENTED_REPLY,
            }
        else:
            pending_steps = [(tool_id, arguments, "result")]
            result = None
            trip_query = _extract_trip_name(message) if tool_id == "get_trips" else None

            if used_selected_trip and tool_id == "get_trip_timeline":
                pending_steps.insert(
                    0,
                    ("get_trip", {"trip_id": arguments["trip_id"]}, "validation"),
                )

            while pending_steps and len(runtime_steps) < MAX_TRAVEL_STEPS:
                current_tool_id, current_arguments, step_purpose = pending_steps.pop(0)
                runtime_response, runtime_ms = _execute_runtime_read(
                    current_tool_id,
                    current_arguments,
                    role=role,
                )
                runtime_steps.append(
                    {
                        "step": len(runtime_steps) + 1,
                        "tool_id": current_tool_id,
                        "runtime_ms": runtime_ms,
                    }
                )

                if not runtime_response.get("success"):
                    result = _runtime_failure_result(
                        current_tool_id,
                        current_arguments,
                        runtime_response,
                    )
                    break

                runtime_result = runtime_response.get("result")
                if step_purpose == "validation":
                    trip = _extract_runtime_trip(runtime_result)
                    if trip is None:
                        updated_context = {}
                        result = {
                            "action": "needs_context",
                            "reply": _TRIP_NOT_FOUND_REPLY,
                        }
                        break
                    updated_context = _context_from_trip(trip)
                    continue

                if current_tool_id == "get_trips" and trip_query is not None:
                    candidates = _find_trip_candidates(runtime_result, trip_query)
                    if not candidates:
                        result = {
                            "action": "needs_context",
                            "reply": _TRIP_NOT_FOUND_REPLY,
                        }
                        break
                    if len(candidates) > 1:
                        result = {
                            "action": "needs_context",
                            "reply": _MULTIPLE_TRIPS_REPLY,
                            "candidates": _redact_value(candidates),
                        }
                        break

                    trip_id = candidates[0].get("id")
                    if not isinstance(trip_id, str) or not trip_id.strip():
                        result = {
                            "action": "runtime_error",
                            "tool_id": current_tool_id,
                            "arguments": current_arguments,
                            "reply": _RUNTIME_ERROR_REPLY,
                        }
                        break
                    pending_steps.append(
                        ("get_trip", {"trip_id": trip_id.strip()}, "result")
                    )
                    continue

                result = _runtime_success_result(
                    current_tool_id,
                    current_arguments,
                    runtime_result,
                )
                if current_tool_id == "get_trip":
                    trip = _extract_runtime_trip(runtime_result)
                    if trip is None and used_selected_trip:
                        updated_context = {}
                    elif trip is not None:
                        updated_context = _context_from_trip(trip)
                break

            if result is None:
                result = {
                    "action": "needs_context",
                    "reply": _MAX_STEPS_REPLY,
                }

    if updated_context or context_was_provided:
        result["updated_context"] = _redact_value(updated_context)

    if debug:
        timings_ms = {}
        if isinstance(proposal_debug, dict):
            proposal_timings = proposal_debug.get("timings_ms")
            if isinstance(proposal_timings, dict):
                timings_ms.update(
                    {
                        key: value
                        for key, value in proposal_timings.items()
                        if key != "total"
                    }
                )
        timings_ms.update(
            {
                "proposal_total": proposal_total,
                "runtime_execute": round(
                    sum(step["runtime_ms"] for step in runtime_steps), 3
                ),
                "total": _elapsed_ms(total_started),
            }
        )
        result["debug"] = {
            "timings_ms": timings_ms,
            "steps": runtime_steps,
            "max_steps": MAX_TRAVEL_STEPS,
        }
        if isinstance(proposal_debug, dict) and "openai_adapter" in proposal_debug:
            result["debug"]["openai_adapter"] = proposal_debug["openai_adapter"]
    return result


def _sanitize_context(context: Any) -> dict[str, Any]:
    """Keep only bounded conversation fields owned by the server orchestrator."""
    if not isinstance(context, dict):
        return {}
    trip_id = context.get("selected_trip_id")
    if not isinstance(trip_id, str) or not trip_id.strip() or len(trip_id) > 256:
        return {}
    sanitized = {"selected_trip_id": trip_id.strip()}
    title = context.get("selected_trip_title")
    if isinstance(title, str) and title.strip() and len(title) <= 500:
        sanitized["selected_trip_title"] = title.strip()
    return sanitized


def _apply_selected_trip_context(
    message: str,
    proposal: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Resolve explicit selected-trip references without accepting LLM context writes."""
    trip_id = context.get("selected_trip_id")
    intent = _selected_trip_intent(message)
    if not isinstance(trip_id, str) or intent is None:
        return proposal, False
    return {
        "action": "tool_proposal",
        "tool_id": intent,
        "arguments": {"trip_id": trip_id},
        "confidence": proposal["confidence"],
        "reply": proposal["reply"],
    }, True


def _selected_trip_intent(message: Any) -> str | None:
    if not isinstance(message, str):
        return None
    normalized = unicodedata.normalize("NFKC", message)
    compact = "".join(character for character in normalized if not character.isspace())
    if re.search(r"(?:[0-9]+|[一二三四五六七八九十]+)日目", compact):
        return "get_trip_timeline"
    if "この旅行" in compact and any(
        token in compact for token in ("詳細", "メモ", "情報", "見せ", "教えて", "開いて")
    ):
        return "get_trip"
    return None


def _extract_runtime_trip(runtime_result: Any) -> dict[str, Any] | None:
    if not isinstance(runtime_result, dict):
        return None
    trip = runtime_result.get("trip")
    if not isinstance(trip, dict):
        return None
    trip_id = trip.get("id")
    if not isinstance(trip_id, str) or not trip_id.strip():
        return None
    return trip


def _context_from_trip(trip: dict[str, Any]) -> dict[str, Any]:
    context = {"selected_trip_id": trip["id"].strip()}
    title = trip.get("title")
    if isinstance(title, str) and title.strip():
        context["selected_trip_title"] = title.strip()
    return context


def _execute_runtime_read(
    tool_id: str,
    arguments: dict[str, Any],
    *,
    role: str,
) -> tuple[dict[str, Any], float]:
    """Apply Chat policy immediately before every Runtime execution."""
    runtime_started = perf_counter()
    try:
        validated_call = validate_chat_proposal(
            {
                "action": "tool_proposal",
                "tool_id": tool_id,
                "arguments": arguments,
                "confidence": "high",
                "reply": "server-side runtime step",
            }
        )
        execution_policy = get_chat_tool_execution_policy(validated_call["tool_id"])
        if execution_policy != "read_executable":
            return {"success": False}, _elapsed_ms(runtime_started)
        # role and confirmed are server-owned values, never model output.
        return (
            runtime_service.execute_stub(
                validated_call["tool_id"],
                params=validated_call["arguments"],
                confirmed=False,
                role=role,
            ),
            _elapsed_ms(runtime_started),
        )
    except Exception:
        # Runtime exception details can contain backend or credential data.
        return {"success": False}, _elapsed_ms(runtime_started)


def _runtime_failure_result(
    tool_id: str,
    arguments: dict[str, Any],
    runtime_response: dict[str, Any],
) -> dict[str, Any]:
    if runtime_response.get("permission_denied"):
        action = "permission_denied"
        reply = _PERMISSION_DENIED_REPLY
    else:
        action = "runtime_error"
        reply = _RUNTIME_ERROR_REPLY
    return {
        "action": action,
        "tool_id": tool_id,
        "arguments": _redact_value(arguments),
        "reply": reply,
    }


def _runtime_success_result(
    tool_id: str,
    arguments: dict[str, Any],
    runtime_result: Any,
) -> dict[str, Any]:
    safe_arguments = _redact_value(arguments)
    result = {
        "action": "tool_result",
        "tool_id": tool_id,
        "arguments": safe_arguments,
        "reply": _SUCCESS_REPLIES[tool_id],
        "result": _redact_value(runtime_result),
    }
    if tool_id == "get_trip":
        trip = runtime_result.get("trip") if isinstance(runtime_result, dict) else None
        if not isinstance(trip, dict):
            return {
                "action": "needs_context",
                "reply": _TRIP_NOT_FOUND_REPLY,
            }
        title = trip.get("title") if isinstance(trip, dict) else None
        result["reply"] = (
            f"{redact_sensitive_text(title)}を開きます。"
            if isinstance(title, str) and title.strip()
            else "旅行を開きます。"
        )
        result["navigation"] = {
            "type": "travel_trip",
            "target": f"#travel?trip_id={quote(safe_arguments['trip_id'], safe='')}",
            "trip_id": safe_arguments["trip_id"],
            "label": "Travelで開く",
        }
    return result


def _extract_trip_name(message: str) -> str | None:
    """Extract a conservative trip-name query from a get_trips utterance."""
    if not isinstance(message, str):
        return None
    value = unicodedata.normalize("NFKC", message).strip()
    value = "".join(character for character in value if not character.isspace())
    value = value.rstrip("。.!！?？")
    for suffix in (
        "を開いてください",
        "開いてください",
        "を表示してください",
        "表示してください",
        "を見せてください",
        "見せてください",
        "を開いて",
        "開いて",
        "を表示して",
        "表示して",
        "を見せて",
        "見せて",
        "を開く",
        "開く",
    ):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    value = value.strip("「」『』\"'")
    normalized = _normalize_trip_text(value)
    if normalized in {"", "旅行", "旅", "旅行一覧", "旅一覧", "trip", "trips"}:
        return None
    return normalized


def _find_trip_candidates(
    runtime_result: Any,
    normalized_query: str,
) -> list[dict[str, Any]]:
    if not isinstance(runtime_result, dict):
        return []
    trips = runtime_result.get("trips")
    if not isinstance(trips, list):
        return []
    candidates = []
    for trip in trips:
        if not isinstance(trip, dict):
            continue
        title = trip.get("title")
        if isinstance(title, str) and normalized_query in _normalize_trip_text(title):
            candidates.append(trip)
    return candidates


def _normalize_trip_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(character for character in normalized if not character.isspace())


def _redact_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(proposal)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
