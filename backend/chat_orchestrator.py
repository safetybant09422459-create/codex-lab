from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from time import perf_counter
from typing import Any

from .chat_tool_policy import get_chat_tool_execution_policy, validate_chat_proposal
from .chat_core import (
    ComposeRequest,
    ConversationState,
    EntityResolutionRequest,
    EntityResolutionResult,
)
from .openai_adapter import generate_text_with_timings, redact_sensitive_text
from .runtime import RuntimeService
from .travel_chat_adapter import (
    conversation_state_from_legacy_context,
    conversation_state_from_runtime_trip,
    legacy_context_from_conversation_state,
    selected_trip_entity,
)
from .travel_entity_resolver import TravelEntityResolver
from .travel_planner import TravelPlanner, legacy_proposal_from_plan
from .travel_response_composer import TravelResponseComposer


_RUNTIME_ERROR_REPLY = "Toolの実行に失敗しました。時間をおいて再度お試しください。"
_PERMISSION_DENIED_REPLY = "この操作を実行する権限がありません。"
_MAX_STEPS_REPLY = "安全のため処理を中断しました。対象の旅行をもう少し具体的に指定してください。"

MAX_TRAVEL_STEPS = 3

# Reused within the process. Runtime remains the only path to executors/repositories.
runtime_service = RuntimeService()
travel_entity_resolver = TravelEntityResolver()
travel_response_composer = TravelResponseComposer()


def propose_travel_tool(
    user_message: str,
    *,
    context: dict[str, Any] | None = None,
    text_generator: Callable[..., str] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Compatibility facade: create a Plan, then expose the legacy proposal."""
    planner = TravelPlanner(timed_text_generator=generate_text_with_timings)
    plan = planner.create_plan(
        user_message,
        context=context,
        text_generator=text_generator,
        debug=debug,
    )
    return legacy_proposal_from_plan(plan, debug=debug)


def handle_travel_chat(
    message: str,
    role: str = "admin",
    debug: bool = False,
    context: dict[str, Any] | None = None,
    *,
    text_generator: Callable[..., str] | None = None,
    runtime: RuntimeService | None = None,
) -> dict[str, Any]:
    """Execute a bounded server-side Travel read plan proposed by the LLM."""
    total_started = perf_counter()
    proposal_started = perf_counter()
    context_was_provided = context is not None
    conversation_state = conversation_state_from_legacy_context(context)
    updated_context = legacy_context_from_conversation_state(conversation_state)
    planner = TravelPlanner(timed_text_generator=generate_text_with_timings)
    plan = planner.create_plan(
        message,
        context=updated_context,
        text_generator=text_generator,
        debug=debug,
    )
    proposal = legacy_proposal_from_plan(plan, debug=debug)
    proposal_total = _elapsed_ms(proposal_started)

    proposal_debug = proposal.pop("debug", None)
    runtime_steps: list[dict[str, Any]] = []
    resolution_diagnostics: dict[str, Any] | None = None

    if proposal.get("action") != "tool_proposal":
        result = proposal
    else:
        proposal, used_selected_trip = _apply_selected_trip_context(
            message,
            proposal,
            conversation_state,
        )
        tool_id = proposal["tool_id"]
        arguments = proposal["arguments"]
        execution_policy = get_chat_tool_execution_policy(tool_id)

        if execution_policy == "write_requires_pending_action":
            result = travel_response_composer.compose(
                ComposeRequest(
                    outcome="pending_write",
                    plan=plan,
                    conversation_state=conversation_state,
                    tool_id=tool_id,
                    arguments=arguments,
                )
            ).response
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
                    runtime=runtime,
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
                        composed = travel_response_composer.compose(
                            ComposeRequest(
                                outcome="not_found",
                                plan=plan,
                                runtime_result=runtime_result,
                                conversation_state=conversation_state,
                                tool_id=current_tool_id,
                                arguments=current_arguments,
                                clear_context_on_not_found=True,
                            )
                        )
                        conversation_state = composed.conversation_state or (
                            conversation_state_from_legacy_context(None)
                        )
                        updated_context = legacy_context_from_conversation_state(
                            conversation_state
                        )
                        result = composed.response
                        break
                    conversation_state = conversation_state_from_runtime_trip(trip)
                    updated_context = legacy_context_from_conversation_state(
                        conversation_state
                    )
                    continue

                if current_tool_id == "get_trips" and trip_query is not None:
                    resolution, candidates = _resolve_trip_candidates(
                        runtime_result, trip_query
                    )
                    resolution_diagnostics = {
                        "resolver": (resolution.diagnostics or {}).get("resolver"),
                        "resolution_status": resolution.status,
                        "candidate_count": len(resolution.candidates),
                        "top_candidate_score": (
                            resolution.candidates[0].score
                            if resolution.candidates
                            else None
                        ),
                    }
                    if resolution.status == "not_found":
                        result = travel_response_composer.compose(
                            ComposeRequest(
                                outcome="not_found",
                                plan=plan,
                                resolution_result=resolution,
                                runtime_result=runtime_result,
                                conversation_state=conversation_state,
                                tool_id=current_tool_id,
                                arguments=current_arguments,
                            )
                        ).response
                        break
                    if resolution.status == "ambiguous":
                        result = travel_response_composer.compose(
                            ComposeRequest(
                                outcome="candidates",
                                plan=plan,
                                resolution_result=resolution,
                                runtime_result=runtime_result,
                                conversation_state=conversation_state,
                                tool_id=current_tool_id,
                                arguments=current_arguments,
                                candidates=candidates,
                            )
                        ).response
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

                composed = travel_response_composer.compose(
                    ComposeRequest(
                        outcome="success",
                        plan=plan,
                        runtime_result=runtime_result,
                        conversation_state=conversation_state,
                        tool_id=current_tool_id,
                        arguments=current_arguments,
                        clear_context_on_not_found=used_selected_trip,
                    )
                )
                result = composed.response
                if composed.conversation_state is not None:
                    conversation_state = composed.conversation_state
                    updated_context = legacy_context_from_conversation_state(
                        conversation_state
                    )
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
        if resolution_diagnostics is not None:
            result["debug"]["entity_resolution"] = resolution_diagnostics
        if isinstance(proposal_debug, dict) and "openai_adapter" in proposal_debug:
            result["debug"]["openai_adapter"] = proposal_debug["openai_adapter"]
    # Final defense: every public field is redacted after Composer and debug assembly.
    return _redact_value(result)


def _apply_selected_trip_context(
    message: str,
    proposal: dict[str, Any],
    conversation_state: ConversationState,
) -> tuple[dict[str, Any], bool]:
    """Resolve explicit selected-trip references without accepting LLM context writes."""
    entity = selected_trip_entity(conversation_state)
    intent = _selected_trip_intent(message)
    if entity is None or intent is None:
        return proposal, False
    return {
        "action": "tool_proposal",
        "tool_id": intent,
        "arguments": {"trip_id": entity.entity_id},
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


def _execute_runtime_read(
    tool_id: str,
    arguments: dict[str, Any],
    *,
    role: str,
    runtime: RuntimeService | None = None,
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
        service = runtime or runtime_service
        return (
            service.execute_stub(
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
    """Compatibility facade; response assembly belongs to the Composer."""
    composed = travel_response_composer.compose(
        ComposeRequest(
            outcome="success",
            runtime_result=runtime_result,
            tool_id=tool_id,
            arguments=arguments,
        )
    )
    return _redact_value(composed.response)


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


def _resolve_trip_candidates(
    runtime_result: Any,
    normalized_query: str,
) -> tuple[EntityResolutionResult, list[dict[str, Any]]]:
    if not isinstance(runtime_result, dict):
        trips = []
    else:
        raw_trips = runtime_result.get("trips")
        trips = raw_trips if isinstance(raw_trips, list) else []
    resolution = travel_entity_resolver.resolve(
        EntityResolutionRequest(
            query=normalized_query,
            skill_id="travel",
            entity_types=("trip",),
            limit=max(1, len(trips)),
        ),
        runtime_result=runtime_result,
    )
    trips_by_id = {
        trip.get("id"): trip
        for trip in trips
        if isinstance(trip, dict) and isinstance(trip.get("id"), str)
    }
    return resolution, [
        trips_by_id[candidate.entity.entity_id]
        for candidate in resolution.candidates
        if candidate.entity.entity_id in trips_by_id
    ]


def _find_trip_candidates(
    runtime_result: Any,
    normalized_query: str,
) -> list[dict[str, Any]]:
    """Compatibility facade for callers that only need the matched Trip values."""
    _, candidates = _resolve_trip_candidates(runtime_result, normalized_query)
    return candidates


def _normalize_trip_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(character for character in normalized if not character.isspace())


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
