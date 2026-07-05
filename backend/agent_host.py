from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


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
    principal: Principal = Field(default_factory=Principal)


class TurnContext(ContractModel):
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


class Observation(ContractModel):
    result: dict[str, Any]
    provenance: dict[str, Any]
    visibility: str = "unknown"
    limitations: list[str] = Field(default_factory=list)


class LLMInputPayload(ContractModel):
    contract_version: Literal["1"] = "1"
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


class LLMClient(Protocol):
    def complete(self, payload: LLMInputPayload) -> dict[str, Any]: ...


class AgentRuntime(Protocol):
    def get_operation_catalog(self) -> dict[str, Any]: ...

    def execute_provider_operation(
        self,
        provider_id: str,
        operation_id: str,
        arguments: dict[str, Any],
        confirmed: bool = False,
        role: str | None = None,
    ) -> dict[str, Any]: ...


class FakeLLMClient:
    """Deterministic test adapter. It performs no language interpretation."""

    def __init__(self, action: dict[str, Any]) -> None:
        self.action = deepcopy(action)
        self.payloads: list[LLMInputPayload] = []

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]:
        self.payloads.append(payload.model_copy(deep=True))
        return deepcopy(self.action)


class AgentHost:
    """Minimal, provider-neutral entry point for the single agent loop.

    The host assembles contracts and routes an already-selected operation. It
    never interprets natural language or chooses providers and operations.
    """

    def __init__(self, llm_client: LLMClient, runtime: AgentRuntime) -> None:
        self.llm_client = llm_client
        self.runtime = runtime

    def run_turn(self, turn_input: TurnInput) -> AgentTurnResult:
        turn_id = str(uuid4())
        events = [TraceEvent(event="turn_started", metadata={"channel": turn_input.channel})]
        context = self._assemble_context(turn_id, turn_input)
        events.append(TraceEvent(event="context_assembled"))

        catalog = self.runtime.get_operation_catalog()
        events.append(TraceEvent(event="catalog_loaded"))
        payload = self._build_payload(context, catalog)

        raw_action = self.llm_client.complete(payload)
        events.append(TraceEvent(event="llm_called"))
        action = self._validate_action(raw_action, catalog)
        events.append(
            TraceEvent(event="action_validated", metadata={"action": action.action})
        )

        observations: list[Observation] = []
        if isinstance(action, CallOperationAction):
            runtime_result = self.runtime.execute_provider_operation(
                action.provider_id,
                action.operation_id,
                action.arguments,
                confirmed=False,
                role=turn_input.principal.role,
            )
            events.append(
                TraceEvent(
                    event="runtime_called",
                    metadata={
                        "provider_id": action.provider_id,
                        "operation_id": action.operation_id,
                    },
                )
            )
            observations.append(
                Observation(
                    result=runtime_result,
                    provenance={
                        "provider_id": action.provider_id,
                        "operation_id": action.operation_id,
                        "source_refs": [],
                    },
                    limitations=self._runtime_limitations(runtime_result),
                )
            )
            events.append(TraceEvent(event="observation_recorded"))

        return AgentTurnResult(
            action=action,
            observations=observations,
            trace=AgentTrace(turn_id=turn_id, events=events),
        )

    @staticmethod
    def _assemble_context(turn_id: str, turn_input: TurnInput) -> TurnContext:
        return TurnContext(
            turn_id=turn_id,
            session_id=turn_input.session_id,
            principal=turn_input.principal,
            channel=turn_input.channel,
            normalized_input=turn_input.normalized_input,
        )

    @staticmethod
    def _build_payload(
        context: TurnContext, catalog: dict[str, Any]
    ) -> LLMInputPayload:
        return LLMInputPayload(
            **context.model_dump(),
            available_operations=deepcopy(catalog),
            runtime_policy={"max_operations": 1, "confirmation_source": "runtime"},
            prior_observations=[],
        )

    @staticmethod
    def _validate_action(
        raw_action: dict[str, Any], catalog: dict[str, Any]
    ) -> MessageAction | CallOperationAction:
        try:
            action = ACTION_ADAPTER.validate_python(raw_action)
        except ValidationError as exc:
            raise AgentContractError(f"Invalid LLM action: {exc}") from exc
        if isinstance(action, CallOperationAction):
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
