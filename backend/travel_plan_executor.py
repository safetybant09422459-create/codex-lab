from __future__ import annotations

import re
import unicodedata
from time import perf_counter
from typing import Any

from .chat_core import (
    ConversationState,
    EntityResolutionRequest,
    EntityResolutionResult,
    ExecutionRequest,
    ExecutionResult,
    ExecutionEvidence,
    ExecutionStep,
)
from .chat_tool_policy import get_chat_tool_execution_policy, validate_chat_proposal
from .travel_chat_adapter import (
    conversation_state_from_runtime_trip,
    selected_trip_entity,
)
from .travel_entity_resolver import TravelEntityResolver


class TravelPlanExecutor:
    """Execute a bounded Travel Plan without planning or composing a response."""

    executor_id = "travel_plan_executor"

    def __init__(self, *, resolver: TravelEntityResolver | None = None) -> None:
        self._resolver = resolver or TravelEntityResolver()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        state = request.conversation_state
        plan = request.plan
        if plan.requires_context or not plan.tool_candidates:
            return ExecutionResult(
                execution_status="needs_context",
                conversation_state=state,
            )

        candidate = plan.tool_candidates[0]
        tool_id, arguments, used_selected_trip = _apply_selected_trip_context(
            request.user_message,
            candidate.tool_id,
            candidate.arguments,
            state,
        )
        execution_policy = get_chat_tool_execution_policy(tool_id)
        if execution_policy == "write_requires_pending_action":
            return ExecutionResult(
                execution_status="pending_write",
                tool_id=tool_id,
                arguments=arguments,
                conversation_state=state,
            )

        pending_steps = [(tool_id, arguments, "result")]
        runtime_steps: list[ExecutionStep] = []
        evidence: list[ExecutionEvidence] = []
        trip_query = _extract_trip_name(request.user_message) if tool_id == "get_trips" else None
        resolution_result: EntityResolutionResult | None = None

        if used_selected_trip and tool_id == "get_trip_timeline":
            pending_steps.insert(
                0,
                ("get_trip", {"trip_id": arguments["trip_id"]}, "validation"),
            )

        while pending_steps and len(runtime_steps) < request.max_steps:
            current_tool_id, current_arguments, purpose = pending_steps.pop(0)
            runtime_response, runtime_ms = _execute_runtime_read(
                current_tool_id,
                current_arguments,
                role=request.role,
                runtime=request.runtime_service,
            )
            runtime_steps.append(
                ExecutionStep(
                    step=len(runtime_steps) + 1,
                    tool_id=current_tool_id,
                    runtime_ms=runtime_ms,
                )
            )

            if not isinstance(runtime_response, dict) or not runtime_response.get("success"):
                status = (
                    "permission_denied"
                    if isinstance(runtime_response, dict)
                    and runtime_response.get("permission_denied")
                    else "runtime_error"
                )
                return self._result(
                    status,
                    tool_id=current_tool_id,
                    arguments=current_arguments,
                    steps=runtime_steps,
                    state=state,
                    evidence=evidence,
                )

            runtime_result = runtime_response.get("result")
            evidence.append(
                ExecutionEvidence(
                    tool_id=current_tool_id,
                    arguments=current_arguments,
                    result=runtime_result,
                )
            )
            if purpose == "validation":
                trip = _extract_runtime_trip(runtime_result)
                if trip is None:
                    return self._result(
                        "not_found",
                        runtime_result=runtime_result,
                        tool_id=current_tool_id,
                        arguments=current_arguments,
                        steps=runtime_steps,
                        state=state,
                        evidence=evidence,
                        clear_context_on_not_found=True,
                    )
                state = conversation_state_from_runtime_trip(trip)
                continue

            if current_tool_id == "get_trips" and trip_query is not None:
                resolution_result, candidates = _resolve_trip_candidates(
                    runtime_result,
                    trip_query,
                    resolver=request.resolver or self._resolver,
                )
                if resolution_result.status == "not_found":
                    return self._result(
                        "not_found",
                        runtime_result=runtime_result,
                        resolution_result=resolution_result,
                        tool_id=current_tool_id,
                        arguments=current_arguments,
                        steps=runtime_steps,
                        state=state,
                        evidence=evidence,
                    )
                if resolution_result.status == "ambiguous":
                    return self._result(
                        "candidates",
                        runtime_result=runtime_result,
                        resolution_result=resolution_result,
                        tool_id=current_tool_id,
                        arguments=current_arguments,
                        steps=runtime_steps,
                        state=state,
                        candidates=candidates,
                        evidence=evidence,
                    )

                trip_id = candidates[0].get("id") if candidates else None
                if not isinstance(trip_id, str) or not trip_id.strip():
                    return self._result(
                        "runtime_error",
                        tool_id=current_tool_id,
                        arguments=current_arguments,
                        steps=runtime_steps,
                        state=state,
                        evidence=evidence,
                    )
                trip = candidates[0]
                state = conversation_state_from_runtime_trip(trip)
                if _is_answer_question(request.user_message):
                    pending_steps.append(
                        (
                            "get_trip_timeline",
                            {"trip_id": trip_id.strip()},
                            "result",
                        )
                    )
                else:
                    pending_steps.append(
                        ("get_trip", {"trip_id": trip_id.strip()}, "result")
                    )
                continue

            return self._result(
                "success",
                runtime_result=runtime_result,
                resolution_result=resolution_result,
                tool_id=current_tool_id,
                arguments=current_arguments,
                steps=runtime_steps,
                state=state,
                evidence=evidence,
                clear_context_on_not_found=used_selected_trip,
            )

        return self._result(
            "max_steps",
            resolution_result=resolution_result,
            steps=runtime_steps,
            state=state,
            evidence=evidence,
        )

    def _result(
        self,
        status: str,
        *,
        runtime_result: Any = None,
        resolution_result: EntityResolutionResult | None = None,
        tool_id: str | None = None,
        arguments: dict[str, Any] | None = None,
        steps: list[ExecutionStep],
        state: ConversationState,
        candidates: list[dict[str, Any]] | None = None,
        evidence: list[ExecutionEvidence] | None = None,
        clear_context_on_not_found: bool = False,
    ) -> ExecutionResult:
        diagnostics: dict[str, Any] = {"executor": self.executor_id}
        if resolution_result is not None:
            diagnostics["entity_resolution"] = {
                "resolver": (resolution_result.diagnostics or {}).get("resolver"),
                "resolution_status": resolution_result.status,
                "candidate_count": len(resolution_result.candidates),
                "top_candidate_score": (
                    resolution_result.candidates[0].score
                    if resolution_result.candidates
                    else None
                ),
            }
        return ExecutionResult(
            execution_status=status,
            runtime_result=runtime_result,
            resolution_result=resolution_result,
            tool_id=tool_id,
            arguments=arguments or {},
            steps=steps,
            evidence=evidence or [],
            conversation_state=state,
            candidates=candidates or [],
            clear_context_on_not_found=clear_context_on_not_found,
            diagnostics=diagnostics,
        )


def _apply_selected_trip_context(
    message: str,
    tool_id: str,
    arguments: dict[str, Any],
    conversation_state: ConversationState,
) -> tuple[str, dict[str, Any], bool]:
    """Use a selected Trip hint without accepting model-owned context writes."""
    entity = selected_trip_entity(conversation_state)
    intent = _selected_trip_intent(message)
    if entity is None or intent is None:
        return tool_id, arguments, False
    return intent, {"trip_id": entity.entity_id}, True


def _selected_trip_intent(message: Any) -> str | None:
    if not isinstance(message, str):
        return None
    normalized = unicodedata.normalize("NFKC", message)
    compact = "".join(character for character in normalized if not character.isspace())
    if re.search(r"(?:[0-9]+|[一二三四五六七八九十]+)日目", compact):
        return "get_trip_timeline"
    if _is_answer_question(compact):
        return "get_trip_timeline"
    if "この旅行" in compact and any(
        token in compact for token in ("詳細", "メモ", "情報", "見せ", "教えて", "開いて")
    ):
        return "get_trip"
    return None


def _is_answer_question(message: Any) -> bool:
    if not isinstance(message, str):
        return False
    normalized = unicodedata.normalize("NFKC", message)
    compact = "".join(character for character in normalized if not character.isspace())
    return any(
        token in compact
        for token in ("何した", "何をした", "何食べた", "何を食べた", "何食べ", "食事は")
    )


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
    runtime: Any,
) -> tuple[dict[str, Any], float]:
    """Revalidate Chat policy immediately before every Runtime execution."""
    started = perf_counter()
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
        policy = get_chat_tool_execution_policy(validated_call["tool_id"])
        if policy != "read_executable":
            return {"success": False}, _elapsed_ms(started)
        return (
            runtime.execute_stub(
                validated_call["tool_id"],
                params=validated_call["arguments"],
                confirmed=False,
                role=role,
            ),
            _elapsed_ms(started),
        )
    except Exception:
        return {"success": False}, _elapsed_ms(started)


def _extract_trip_name(message: str) -> str | None:
    """Extract the existing conservative Trip query from a get_trips utterance."""
    if not isinstance(message, str):
        return None
    value = unicodedata.normalize("NFKC", message).strip()
    value = "".join(character for character in value if not character.isspace())
    value = value.rstrip("。.!！?？")
    for suffix in (
        "って何を食べた",
        "って何食べた",
        "で何を食べた",
        "で何食べた",
        "って何をした",
        "って何した",
        "で何をした",
        "で何した",
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
    *,
    resolver: TravelEntityResolver,
) -> tuple[EntityResolutionResult, list[dict[str, Any]]]:
    raw_trips = runtime_result.get("trips") if isinstance(runtime_result, dict) else []
    trips = raw_trips if isinstance(raw_trips, list) else []
    resolution = resolver.resolve(
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
    *,
    resolver: TravelEntityResolver | None = None,
) -> list[dict[str, Any]]:
    _, candidates = _resolve_trip_candidates(
        runtime_result,
        normalized_query,
        resolver=resolver or TravelEntityResolver(),
    )
    return candidates


def _normalize_trip_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(character for character in normalized if not character.isspace())


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
