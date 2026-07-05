from __future__ import annotations

from time import perf_counter
from typing import Any

from .chat_core import (
    ConversationState,
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


class TravelPlanExecutor:
    """Execute a bounded Travel Plan without planning or composing a response."""

    executor_id = "travel_plan_executor"

    def __init__(self, *, resolver: Any = None) -> None:
        # resolver is accepted only to keep construction compatibility while the
        # Python semantic resolver is disabled.
        self._resolver = resolver

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
        trip_query = plan.resolution_query if tool_id == "get_trips" else None
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
                goal=plan.goal,
                answer_mode=plan.answer_mode,
                required_evidence=plan.required_evidence,
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
                # entity_query is LLM-owned intent, not a canonical ID. Python
                # must not interpret it, rank names, or auto-select an entity.
                candidates = _runtime_trip_candidates(runtime_result)
                return self._result(
                    "candidates" if candidates else "not_found",
                    runtime_result=runtime_result,
                    tool_id=current_tool_id,
                    arguments=current_arguments,
                    steps=runtime_steps,
                    state=state,
                    candidates=candidates,
                    evidence=evidence,
                )

            if (
                current_tool_id == "get_trips"
                and plan.goal == "clarify"
                and plan.answer_mode == "clarification"
            ):
                # The Planner has already decided that selection is required.
                # Python only validates and transports Runtime-owned candidates.
                trips = _runtime_trip_candidates(runtime_result)
                return self._result(
                    "candidates",
                    runtime_result=runtime_result,
                    tool_id=current_tool_id,
                    arguments=current_arguments,
                    steps=runtime_steps,
                    state=state,
                    candidates=trips,
                    evidence=evidence,
                )

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
    tool_id: str,
    arguments: dict[str, Any],
    conversation_state: ConversationState,
) -> tuple[str, dict[str, Any], bool]:
    """Use a selected Trip hint without accepting model-owned context writes."""
    entity = selected_trip_entity(conversation_state)
    if tool_id == "get_trips":
        return tool_id, arguments, False
    intent = tool_id if tool_id in {"get_trip", "get_trip_timeline"} else None
    if entity is None or intent is None:
        return tool_id, arguments, False
    return intent, {"trip_id": entity.entity_id}, True


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


def _runtime_trip_candidates(runtime_result: Any) -> list[dict[str, Any]]:
    if not isinstance(runtime_result, dict):
        return []
    trips = runtime_result.get("trips")
    if not isinstance(trips, list):
        return []
    return [
        trip
        for trip in trips
        if isinstance(trip, dict)
        and isinstance(trip.get("id"), str)
        and trip["id"].strip()
    ]


def _execute_runtime_read(
    tool_id: str,
    arguments: dict[str, Any],
    *,
    goal: str,
    answer_mode: str,
    required_evidence: list[str],
    role: str,
    runtime: Any,
) -> tuple[dict[str, Any], float]:
    """Revalidate Chat policy immediately before every Runtime execution."""
    started = perf_counter()
    try:
        validated_call = validate_chat_proposal(
            {
                "action": "tool_proposal",
                "goal": goal,
                "answer_mode": answer_mode,
                "required_evidence": required_evidence,
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


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
