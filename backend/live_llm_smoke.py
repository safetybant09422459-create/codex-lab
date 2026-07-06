from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .agent_host import AgentContractError, AgentHost, TurnInput
from .openai_adapter import (
    OpenAIIncompleteResponseError,
    OpenAIModelProviderAdapter,
    OpenAIModelRefusalError,
    OpenAIRequestError,
    OpenAIResponseValidationError,
    OpenAITimeoutError,
)
from .runtime import RuntimeService


@dataclass(frozen=True)
class SmokeResult:
    success: bool
    answer_returned: bool = False
    call_operation_returned: bool = False
    runtime_provider_called: bool = False
    answer_after_observation: bool = False
    failure_category: str | None = None
    failure_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_live_llm_smoke() -> SmokeResult:
    """Exercise the real adapter and Agent Host without using the Chat API."""
    host = AgentHost(OpenAIModelProviderAdapter(), RuntimeService())
    try:
        greeting = host.run_turn(_turn("live-smoke-answer", "こんにちは"))
        answer_returned = greeting.action.action == "answer"

        travel = host.run_turn(_turn("live-smoke-travel", "旅行一覧見せて"))
        validated_actions = [
            event.metadata.get("action")
            for event in travel.trace.events
            if event.event == "action_validated"
        ]
        call_operation_returned = validated_actions[:1] == ["call_operation"]
        runtime_provider_called = bool(
            travel.observations
            and travel.observations[0].provenance.get("provider_id") == "travel"
            and travel.observations[0].provenance.get("operation_id") == "get_trips"
            and travel.observations[0].raw_result.get("success") is True
        )
        answer_after_observation = bool(
            travel.observations and travel.action.action == "answer"
        )
        success = all(
            (
                answer_returned,
                call_operation_returned,
                runtime_provider_called,
                answer_after_observation,
            )
        )
        refused = (
            greeting.action.action == "refuse" or travel.action.action == "refuse"
        )
        return SmokeResult(
            success=success,
            answer_returned=answer_returned,
            call_operation_returned=call_operation_returned,
            runtime_provider_called=runtime_provider_called,
            answer_after_observation=answer_after_observation,
            failure_category=(
                None if success else "model_refusal" if refused else "unexpected_action"
            ),
            failure_message=(
                None
                if success
                else "LLM action sequence did not match smoke expectations"
            ),
        )
    except Exception as exc:
        return SmokeResult(
            success=False,
            failure_category=_failure_category(exc),
            failure_message=str(exc),
        )


def _turn(session_id: str, text: str) -> TurnInput:
    return TurnInput(
        session_id=session_id,
        channel="smoke",
        normalized_input={"text": text},
    )


def _failure_category(exc: Exception) -> str:
    if isinstance(exc, OpenAIResponseValidationError):
        return "schema_violation"
    if isinstance(exc, AgentContractError):
        return "schema_violation"
    if isinstance(exc, OpenAITimeoutError):
        return "timeout"
    if isinstance(exc, OpenAIModelRefusalError):
        return "model_refusal"
    if isinstance(exc, OpenAIIncompleteResponseError):
        return "incomplete"
    if isinstance(exc, OpenAIRequestError):
        return "provider_request"
    return "runtime"
