from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .conversation_context import ConversationContextBuilder
from .chat_trace import ChatTraceRecorder
from .conversation_state import (
    ConversationTurnState,
    InMemoryConversationStateStore,
)
from .core_models import ConversationTurn
from .entity_context import EntityContextBuilder
from .llm_client import LLMClient
from .observation import ObservationEnvelope, ObservationEnvelopeBuilder


class AgentContractError(ValueError):
    """Raised when an AI model returns data outside the LLM contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Principal(ContractModel):
    role: Literal["admin", "family", "guest"] = "guest"
    subject_id: str | None = None


class TurnInput(ContractModel):
    session_id: str
    channel: str = Field(min_length=1)
    normalized_input: dict[str, Any]
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    principal: Principal = Field(default_factory=Principal)


class TurnContext(ContractModel):
    context_version: str
    turn_id: str
    session_id: str
    principal: Principal
    channel: str
    normalized_input: dict[str, Any]
    conversation_context: list[dict[str, Any]] = Field(default_factory=list)
    conversation_state: dict[str, Any] = Field(default_factory=dict)
    persona_context: dict[str, Any] = Field(default_factory=dict)
    memory_context: list[dict[str, Any]] = Field(default_factory=list)
    activation_candidates: list[dict[str, Any]] = Field(default_factory=list)
    session_info: dict[str, Any]
    capability_context: list[dict[str, Any]] = Field(default_factory=list)


Observation = ObservationEnvelope


class LLMInputPayload(ContractModel):
    contract_version: Literal["1"] = "1"
    context_version: Literal["1"] = "1"
    turn_id: str
    session_id: str
    principal: Principal
    channel: str
    normalized_input: dict[str, Any]
    conversation_context: list[dict[str, Any]]
    conversation_state: dict[str, Any]
    persona_context: dict[str, Any]
    memory_context: list[dict[str, Any]]
    activation_candidates: list[dict[str, Any]]
    session_info: dict[str, Any] = Field(default_factory=dict)
    capability_context: list[dict[str, Any]] = Field(default_factory=list)
    available_operations: dict[str, Any]
    runtime_policy: dict[str, Any]
    prior_observations: list[Observation]


Transition = Literal[
    "continue_topic",
    "switch_topic",
    "answer_pending_question",
    "respond_to_confirmation",
    "start_request",
    "continue_unresolved_intent",
    "end_conversation",
]


class ConversationUpdate(ContractModel):
    transition: Transition
    current_topic: str | None = None
    previous_topic: str | None = None
    active_entities: list[dict[str, Any]] | None = None
    pending_question: str | None = None
    unresolved_intent: str | None = None


class MessageAction(ContractModel):
    contract_version: Literal["1"]
    action: Literal["answer", "ask_clarification", "request_confirmation", "refuse"]
    message: str = Field(min_length=1)
    conversation_update: ConversationUpdate


class CallOperationAction(ContractModel):
    contract_version: Literal["1"]
    action: Literal["call_operation"]
    provider_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    arguments: dict[str, Any]
    conversation_update: ConversationUpdate


LLMAction = Annotated[
    MessageAction | CallOperationAction,
    Field(discriminator="action"),
]
ACTION_ADAPTER = TypeAdapter(LLMAction)


class TraceEvent(ContractModel):
    event: Literal[
        "turn_started",
        "context_assembled",
        "catalog_loaded",
        "llm_called",
        "action_validated",
        "runtime_called",
        "observation_recorded",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(ContractModel):
    turn_id: str
    events: list[TraceEvent]


class AgentTurnResult(ContractModel):
    action: LLMAction
    observations: list[Observation]
    trace: AgentTrace


class AgentRuntime(Protocol):
    def get_operation_catalog(self) -> dict[str, Any]: ...

    def get_capability_catalog(self) -> dict[str, Any]: ...

    def execute_provider_operation(
        self,
        provider_id: str,
        operation_id: str,
        arguments: dict[str, Any],
        confirmed: bool = False,
        role: str | None = None,
    ) -> dict[str, Any]: ...

    def get_observation_details(
        self, provider_id: str, operation_id: str, result: dict[str, Any]
    ) -> dict[str, Any]: ...


class AgentHost:
    """Minimal, provider-neutral entry point for the single agent loop.

    The host assembles contracts and routes an already-selected operation. It
    never interprets natural language or chooses providers and operations.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        runtime: AgentRuntime,
        conversation_store: InMemoryConversationStateStore | None = None,
        context_builder: ConversationContextBuilder | None = None,
        observation_builder: ObservationEnvelopeBuilder | None = None,
        entity_context_builder: EntityContextBuilder | None = None,
        trace_recorder: ChatTraceRecorder | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.runtime = runtime
        self.conversation_store = (
            conversation_store or InMemoryConversationStateStore()
        )
        self.context_builder = context_builder or ConversationContextBuilder()
        self.observation_builder = observation_builder or ObservationEnvelopeBuilder()
        self.entity_context_builder = entity_context_builder or EntityContextBuilder()
        self.trace_recorder = trace_recorder

    def reset_conversation(self, session_id: str) -> None:
        self.conversation_store.clear_session(session_id)

    def run_turn(self, turn_input: TurnInput) -> AgentTurnResult:
        turn_id = str(uuid4())
        recorder = self.trace_recorder
        if recorder:
            recorder.start_turn(
                turn_id, turn_input.session_id, turn_input.normalized_input
            )
        events = [TraceEvent(event="turn_started", metadata={"channel": turn_input.channel})]
        try:
            if recorder:
                recorder.stage_start(turn_id, "context_assembly", turn_input)
            context = self._assemble_context(turn_id, turn_input)
            if recorder:
                recorder.stage_finish(turn_id, "context_assembly", {
                    "turn_context": context,
                    "conversation_context_count": len(context.conversation_context),
                    "activation_candidates_count": len(context.activation_candidates),
                    "capability_context_count": len(context.capability_context),
                    "memory_context_count": len(context.memory_context),
                    "session_info": context.session_info,
                })
            events.append(TraceEvent(event="context_assembled"))

            if recorder:
                recorder.stage_start(turn_id, "operation_catalog")
            catalog = self.runtime.get_operation_catalog()
            if recorder:
                operations = [
                    operation
                    for provider in catalog.get("providers", [])
                    for operation in provider.get("operations", [])
                ]
                recorder.stage_finish(turn_id, "operation_catalog", {
                    "provider_count": len(catalog.get("providers", [])),
                    "operation_count": len(operations),
                    "implemented_operation_count": sum(operation.get("availability") == "implemented" for operation in operations),
                    "available_operation_names": [f"{operation.get('provider_id')}.{operation.get('operation_id')}" for operation in operations if operation.get("availability") == "implemented"],
                    "catalog": catalog,
                })
            events.append(TraceEvent(event="catalog_loaded"))
            observations: list[Observation] = []
            action: MessageAction | CallOperationAction
            for step in range(1, 3):
                llm_stage = f"llm_call_{step}"
                validation_stage = f"action_validation_{step}"
                payload = self._build_payload(context, catalog, observations)
                if recorder:
                    recorder.stage_start(turn_id, llm_stage, payload)
                try:
                    raw_action = self.llm_client.complete(payload)
                except Exception as exc:
                    if recorder:
                        recorder.stage_error(turn_id, llm_stage, _exception_category(exc), exc)
                    raise
                if recorder:
                    recorder.stage_finish(turn_id, llm_stage, raw_action)
                events.append(TraceEvent(event="llm_called", metadata={"step": step}))
                if recorder:
                    recorder.stage_start(turn_id, validation_stage, raw_action)
                try:
                    action = self._validate_action(raw_action, catalog, operation_call_allowed=step < 2)
                except Exception as exc:
                    if recorder:
                        recorder.stage_error(turn_id, validation_stage, "action_validation_error", exc)
                    raise
                if recorder:
                    recorder.stage_finish(turn_id, validation_stage, action)
                events.append(TraceEvent(event="action_validated", metadata={"step": step, "action": action.action}))

                if not isinstance(action, CallOperationAction):
                    break

                runtime_input = {
                    "provider_id": action.provider_id, "operation_id": action.operation_id,
                    "llm_arguments": action.arguments, "runtime_arguments": action.arguments,
                    "role": turn_input.principal.role, "confirmed": False,
                    "permission": "not_exposed", "confirmation": "not_exposed",
                }
                if recorder:
                    recorder.stage_start(turn_id, "runtime_execution", runtime_input)
                try:
                    runtime_result = self.runtime.execute_provider_operation(
                        action.provider_id, action.operation_id, action.arguments,
                        confirmed=False, role=turn_input.principal.role,
                    )
                except Exception as exc:
                    if recorder:
                        recorder.stage_error(turn_id, "runtime_execution", _runtime_error_category(exc), exc)
                    raise
                if recorder:
                    recorder.stage_finish(turn_id, "runtime_execution", runtime_result, status="success" if runtime_result.get("success") else "warning")
                events.append(TraceEvent(event="runtime_called", metadata={"step": step, "provider_id": action.provider_id, "operation_id": action.operation_id}))
                if recorder:
                    recorder.stage_start(turn_id, "observation_build", {"provider_id": action.provider_id, "operation_id": action.operation_id, "raw_result": runtime_result})
                try:
                    details = self.runtime.get_observation_details(action.provider_id, action.operation_id, runtime_result)
                    if not isinstance(details, dict):
                        details = {}
                    details["limitations"] = [*details.get("limitations", ()), *self._runtime_limitations(runtime_result)]
                    observation = self.observation_builder.build(
                        provider_id=action.provider_id, operation_id=action.operation_id,
                        raw_result=runtime_result, details=details,
                    )
                    observations.append(observation)
                except Exception as exc:
                    if recorder:
                        recorder.stage_error(turn_id, "observation_build", "observation_error", exc)
                    raise
                if recorder:
                    recorder.stage_finish(turn_id, "observation_build", observation)
                events.append(TraceEvent(event="observation_recorded", metadata={"step": step}))

            if recorder:
                recorder.stage_start(turn_id, "final_answer", action)
            final_answer = action.message if isinstance(action, MessageAction) else None
            if not final_answer:
                error = AgentContractError("Final answer is missing")
                if recorder:
                    recorder.stage_error(turn_id, "final_answer", "final_answer_missing", error)
                raise error
            if recorder:
                recorder.stage_finish(turn_id, "final_answer", {"message": final_answer})
            result = AgentTurnResult(action=action, observations=observations, trace=AgentTrace(turn_id=turn_id, events=events))
            self._remember_turn(turn_input, result)
            if recorder:
                recorder.complete(turn_id, final_answer)
            return result
        except Exception as exc:
            if recorder:
                recorder.complete(turn_id, error_category=_exception_category(exc), error=exc)
            raise

    def _assemble_context(self, turn_id: str, turn_input: TurnInput) -> TurnContext:
        previous_turns = self.conversation_store.get_turns(turn_input.session_id)
        if not previous_turns:
            previous_turns = self._channel_history_turns(
                turn_input.conversation_history
            )
        capability_catalog = self.runtime.get_capability_catalog()
        if not isinstance(capability_catalog, dict):
            capability_catalog = {"providers": []}
        assembled = self.context_builder.build(
            session_id=turn_input.session_id,
            channel=turn_input.channel,
            conversation_started_at=self.conversation_store.get_or_create_started_at(
                turn_input.session_id
            ),
            previous_turns=previous_turns,
            capabilities=capability_catalog.get("providers", []),
            allowed_visibilities=self._allowed_visibilities(turn_input.principal.role),
        )
        return TurnContext(
            turn_id=turn_id,
            session_id=turn_input.session_id,
            principal=turn_input.principal,
            channel=turn_input.channel,
            normalized_input=turn_input.normalized_input,
            **assembled,
        )

    @staticmethod
    def _channel_history_turns(
        history: list[ConversationTurn],
    ) -> list[ConversationTurnState]:
        """Project completed client pairs as untrusted context, never Core state."""
        turns: list[ConversationTurnState] = []
        pending_user: str | None = None
        for item in history:
            if item.role == "user":
                pending_user = item.content
            elif pending_user is not None:
                turns.append(
                    ConversationTurnState(
                        user_input={"text": pending_user},
                        assistant_final_response=item.content,
                        last_llm_action={},
                        source="client_history_hint",
                    )
                )
                pending_user = None
        return turns

    @staticmethod
    def _allowed_visibilities(role: str) -> frozenset[str]:
        return {
            "admin": frozenset({"public", "shared", "family", "private", "unknown"}),
            "family": frozenset({"public", "shared", "family", "unknown"}),
            "guest": frozenset({"public", "shared", "unknown"}),
        }[role]

    def _remember_turn(
        self, turn_input: TurnInput, result: AgentTurnResult
    ) -> None:
        action = result.action
        if not isinstance(action, MessageAction):
            return
        self.conversation_store.append_turn(
            turn_input.session_id,
            ConversationTurnState(
                user_input=deepcopy(turn_input.normalized_input),
                assistant_final_response=action.message,
                last_llm_action=action.model_dump(mode="json"),
                last_observations=[
                    observation.model_dump(mode="json")
                    for observation in result.observations
                ],
                active_entities=self.entity_context_builder.build(
                    result.observations,
                    action.conversation_update.active_entities or [],
                ),
            ),
        )

    @staticmethod
    def _build_payload(
        context: TurnContext,
        catalog: dict[str, Any],
        observations: list[Observation],
    ) -> LLMInputPayload:
        return LLMInputPayload(
            **context.model_dump(),
            available_operations=deepcopy(catalog),
            runtime_policy={
                "max_steps": 2,
                "max_operations": 1,
                "confirmation_source": "runtime",
            },
            prior_observations=deepcopy(observations),
        )

    @staticmethod
    def _validate_action(
        raw_action: dict[str, Any],
        catalog: dict[str, Any],
        *,
        operation_call_allowed: bool,
    ) -> MessageAction | CallOperationAction:
        try:
            action = ACTION_ADAPTER.validate_python(raw_action)
        except ValidationError as exc:
            raise AgentContractError(f"Invalid LLM action: {exc}") from exc
        if isinstance(action, CallOperationAction):
            if not operation_call_allowed:
                raise AgentContractError(
                    "LLM returned call_operation after the operation budget was exhausted"
                )
            matching = [
                operation
                for provider in catalog.get("providers", [])
                if provider.get("provider_id") == action.provider_id
                for operation in provider.get("operations", [])
                if operation.get("operation_id") == action.operation_id
            ]
            if len(matching) != 1:
                raise AgentContractError(
                    f"Action references unknown operation: "
                    f"{action.provider_id}.{action.operation_id}"
                )
            if matching[0].get("availability") != "implemented":
                raise AgentContractError(
                    f"Action references non-executable operation: "
                    f"{action.provider_id}.{action.operation_id}"
                )
        return action

    @staticmethod
    def _runtime_limitations(runtime_result: dict[str, Any]) -> list[str]:
        limitations: list[str] = []
        execution_mode = runtime_result.get("execution_mode")
        if execution_mode and "stub" in str(execution_mode):
            limitations.append("stub")
        if runtime_result.get("blocked"):
            limitations.append("blocked")
        return limitations


def _exception_category(exc: Exception) -> str:
    name = exc.__class__.__name__
    return {
        "OpenAIConfigurationError": "configuration_error",
        "OpenAITimeoutError": "timeout",
        "OpenAIModelRefusalError": "provider_refusal",
        "OpenAIIncompleteResponseError": "provider_incomplete",
        "OpenAIResponseValidationError": "malformed_response",
        "OpenAIRequestError": "provider_request_error",
        "AgentContractError": "action_validation_error",
    }.get(name, "internal_error")


def _runtime_error_category(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "permission" in name or "permission" in message:
        return "permission_denied"
    if "confirmation" in name or "confirmation" in message:
        return "confirmation_required"
    if "notexecutable" in name or "not allowed" in message:
        return "operation_not_allowed"
    return "runtime_error"
