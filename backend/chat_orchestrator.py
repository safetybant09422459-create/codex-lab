from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from .chat_core import ComposeRequest, ExecutionRequest
from .openai_adapter import generate_text_with_timings, redact_sensitive_text
from .runtime import RuntimeService
from .travel_chat_adapter import (
    conversation_state_from_legacy_context,
    legacy_context_from_conversation_state,
)
from .travel_entity_resolver import TravelEntityResolver
from .travel_plan_executor import (
    TravelPlanExecutor,
    _extract_trip_name,
    _find_trip_candidates as find_trip_candidates,
)
from .travel_planner import TravelPlanner, legacy_proposal_from_plan
from .travel_response_composer import TravelResponseComposer


MAX_TRAVEL_STEPS = 3

# Reused within the process. Runtime remains the only path to executors/repositories.
runtime_service = RuntimeService()
travel_entity_resolver = TravelEntityResolver()
travel_plan_executor = TravelPlanExecutor(resolver=travel_entity_resolver)
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
    """Plan, execute, and compose one bounded server-side Travel request."""
    total_started = perf_counter()
    proposal_started = perf_counter()
    context_was_provided = context is not None
    conversation_state = conversation_state_from_legacy_context(context)
    planner = TravelPlanner(timed_text_generator=generate_text_with_timings)
    plan = planner.create_plan(
        message,
        context=legacy_context_from_conversation_state(conversation_state),
        text_generator=text_generator,
        debug=debug,
    )
    proposal = legacy_proposal_from_plan(plan, debug=debug)
    proposal_total = _elapsed_ms(proposal_started)
    proposal_debug = proposal.get("debug")

    execution = travel_plan_executor.execute(
        ExecutionRequest(
            plan=plan,
            user_message=message,
            conversation_state=conversation_state,
            role=role,
            debug=debug,
            runtime_service=runtime or runtime_service,
            resolver=travel_entity_resolver,
            max_steps=MAX_TRAVEL_STEPS,
        )
    )
    execution_state = execution.conversation_state or conversation_state
    composed = travel_response_composer.compose(
        ComposeRequest(
            outcome=execution.execution_status,
            plan=plan,
            resolution_result=execution.resolution_result,
            runtime_result=execution.runtime_result,
            conversation_state=execution_state,
            tool_id=execution.tool_id,
            arguments=execution.arguments,
            candidates=execution.candidates,
            diagnostics=execution.diagnostics,
            clear_context_on_not_found=execution.clear_context_on_not_found,
        )
    )
    result = composed.response
    conversation_state = composed.conversation_state or execution_state
    updated_context = legacy_context_from_conversation_state(conversation_state)

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
        runtime_steps = [step.model_dump() for step in execution.steps]
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
        diagnostics = execution.diagnostics or {}
        if "entity_resolution" in diagnostics:
            result["debug"]["entity_resolution"] = diagnostics[
                "entity_resolution"
            ]
        if isinstance(proposal_debug, dict) and "openai_adapter" in proposal_debug:
            result["debug"]["openai_adapter"] = proposal_debug["openai_adapter"]

    # Final defense: every public field is redacted after Composer and debug assembly.
    return _redact_value(result)


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


def _find_trip_candidates(
    runtime_result: Any,
    normalized_query: str,
) -> list[dict[str, Any]]:
    """Compatibility facade for callers that only need matched Trip values."""
    return find_trip_candidates(
        runtime_result,
        normalized_query,
        resolver=travel_entity_resolver,
    )


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
