from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .openai_adapter import redact_sensitive_text


class ChatCoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityRef(ChatCoreModel):
    skill_id: str
    entity_type: str
    entity_id: str
    label: str
    source: str
    verified_at: datetime | None = None


class EntityCandidate(ChatCoreModel):
    entity: EntityRef
    score: float = Field(ge=0.0, le=1.0)
    matched_by: str


class EntityResolutionRequest(ChatCoreModel):
    """Skill-neutral request passed to an EntityResolver."""

    query: str = Field(min_length=1)
    skill_id: str | None = None
    entity_types: tuple[str, ...] | None = None
    context: dict[str, Any] | None = None
    limit: int = Field(default=20, ge=1)


class EntityResolutionResult(ChatCoreModel):
    """Skill-neutral resolution state produced from ranked candidates."""

    status: Literal["resolved", "ambiguous", "not_found", "needs_context"]
    candidates: list[EntityCandidate] = Field(default_factory=list)
    resolved_entity: EntityRef | None = None
    reason: str | None = None
    diagnostics: dict[str, Any] | None = None


class ConversationState(ChatCoreModel):
    active_skill: str | None = None
    selected_entities: list[EntityRef] = Field(default_factory=list)
    skill_slots: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(ChatCoreModel):
    """One recent message used as ephemeral Planner working context."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ConversationWorkingContext(ChatCoreModel):
    """Recent conversation only; this is neither state nor persisted Memory."""

    turns: list[ConversationTurn] = Field(default_factory=list, max_length=5)


class PlanToolCandidate(ChatCoreModel):
    """One validated Tool option proposed for a Plan."""

    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)


class Plan(ChatCoreModel):
    """Skill-neutral description of what Chat intends to do.

    A Plan is descriptive only. It does not resolve entities, execute Tools,
    generate responses, or mutate conversation state.
    """

    intent: str
    # Goal vocabularies belong to each Skill. Core only transports the
    # validated values so Photo, Calendar, and Garden do not depend on Travel.
    goal: str = "clarify"
    answer_mode: str = "none"
    required_evidence: list[str] = Field(default_factory=list)
    target_skill: str | None = None
    target_entity_type: str | None = None
    resolution_query: str | None = None
    tool_candidates: list[PlanToolCandidate] = Field(default_factory=list)
    requires_resolution: bool = False
    requires_context: bool = False
    requires_confirmation: bool = False
    reason: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    diagnostics: dict[str, Any] | None = None


class ExecutionStep(ChatCoreModel):
    """One Runtime attempt made while executing a bounded Plan."""

    step: int = Field(ge=1)
    tool_id: str
    runtime_ms: float = Field(ge=0.0)


class ExecutionEvidence(ChatCoreModel):
    """One successful Runtime result already obtained by a PlanExecutor."""

    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None


class EvidenceBundle(ChatCoreModel):
    """One Skill result prepared as read-only input for an LLM answer."""

    skill_id: str
    tool_id: str
    user_question: str
    result: Any = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    summary_for_llm: str = ""
    limitations: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "high"


class ExecutionRequest(ChatCoreModel):
    """Server-owned inputs required to execute a descriptive Plan."""

    plan: Plan
    user_message: str
    conversation_state: ConversationState
    role: str
    debug: bool = False
    runtime_service: Any
    resolver: Any = None
    max_steps: int = Field(default=3, ge=1)


class ExecutionResult(ChatCoreModel):
    """Execution facts for a ResponseComposer; never a user-facing response."""

    execution_status: Literal[
        "success",
        "needs_context",
        "pending_write",
        "candidates",
        "not_found",
        "runtime_error",
        "permission_denied",
        "max_steps",
    ]
    runtime_result: Any = None
    resolution_result: EntityResolutionResult | None = None
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    steps: list[ExecutionStep] = Field(default_factory=list)
    evidence: list[ExecutionEvidence] = Field(default_factory=list)
    conversation_state: ConversationState | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    clear_context_on_not_found: bool = False
    diagnostics: dict[str, Any] | None = None


class AnswerRequest(ChatCoreModel):
    """Read-only facts available to an AnswerGenerator after execution."""

    user_question: str
    plan: Plan | None = None
    execution_result: ExecutionResult
    conversation_state: ConversationState
    evidence: list[ExecutionEvidence] = Field(default_factory=list)


class AnswerResult(ChatCoreModel):
    """A direct answer grounded only in already acquired Evidence."""

    answer: str
    confidence: Literal["high", "medium", "low"]
    answer_type: Literal[
        "grounded", "activities", "food", "day", "not_applicable"
    ]
    used_evidence: list[ExecutionEvidence] = Field(default_factory=list)
    source: Literal[
        "llm",
        "fallback_static",
    ] = "fallback_static"
    evidence_used: bool = False


class ContentBlock(ChatCoreModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class SuggestedAction(ChatCoreModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None


class ChatResponseV1(ChatCoreModel):
    version: str = "1"
    outcome: str
    message: str
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    conversation_state: ConversationState | None = None
    diagnostics: dict[str, Any] | None = None


class ClarificationResult(ChatCoreModel):
    """Skill-neutral decision produced after execution cannot pick one entity."""

    status: Literal["not_required", "clarification_required", "candidates"]
    clarification: str | None = None
    candidate_list: list[dict[str, Any]] = Field(default_factory=list)
    reason: Literal[
        "query_too_broad",
        "multiple_candidates",
        "low_confidence",
        "missing_context",
    ] | None = None
    recommended_action: Literal[
        "continue",
        "select_candidate",
        "provide_context",
    ] = "continue"


class ComposeRequest(ChatCoreModel):
    """Facts available to a ResponseComposer after orchestration.

    The request is descriptive only. A Composer must not execute a Plan, resolve
    an Entity, or call Runtime while converting these facts into a response.
    """

    outcome: str
    user_message: str = ""
    plan: Plan | None = None
    resolution_result: EntityResolutionResult | None = None
    runtime_result: Any = None
    conversation_state: ConversationState | None = None
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    navigation_hint: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    clear_context_on_not_found: bool = False
    answer_result: AnswerResult | None = None


class ComposeResult(ChatCoreModel):
    """Legacy-compatible output plus the incremental internal V1 contract."""

    response: dict[str, Any]
    response_v1: ChatResponseV1
    conversation_state: ConversationState | None = None


class EntityResolver(Protocol):
    """Common boundary for converting a query into an entity resolution state."""

    def resolve(self, request: EntityResolutionRequest) -> EntityResolutionResult: ...


class Planner(Protocol):
    """Common boundary for turning an LLM proposal into a descriptive Plan."""

    def create_plan(
        self,
        user_message: str,
        *,
        conversation: ConversationWorkingContext | None = None,
        conversation_state: ConversationState | None = None,
        context: dict[str, Any] | None = None,
        text_generator: Callable[..., str] | None = None,
        debug: bool = False,
    ) -> Plan: ...


class PlanExecutor(Protocol):
    """Common boundary for bounded Plan execution through Runtime."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class AnswerGenerator(Protocol):
    """Common boundary for answering from existing Evidence without I/O."""

    def generate(self, request: AnswerRequest) -> AnswerResult: ...


class ResponseComposer(Protocol):
    """Common boundary for turning orchestration facts into a Chat response."""

    def compose(self, request: ComposeRequest) -> ComposeResult: ...


def legacy_chat_response_to_v1(
    response: dict[str, Any],
    *,
    conversation_state: ConversationState | None = None,
    content_blocks: list[ContentBlock] | None = None,
) -> ChatResponseV1:
    """Compose the internal response contract from the current public contract.

    The public API continues to return the legacy fields. This adapter gives new
    callers one stable response shape while migration proceeds incrementally.
    """
    safe_response = _redact_value(response)
    blocks = [
        ContentBlock.model_validate(_redact_value(block.model_dump()))
        for block in (content_blocks or [])
    ]
    if not blocks and safe_response.get("result") is not None:
        blocks.append(
            ContentBlock(
                type="tool_result",
                data={
                    "tool_id": safe_response.get("tool_id"),
                    "result": safe_response["result"],
                },
            )
        )

    actions: list[SuggestedAction] = []
    navigation = safe_response.get("navigation")
    if isinstance(navigation, dict):
        actions.append(
            SuggestedAction(
                type="navigate",
                payload=navigation,
                label=navigation.get("label")
                if isinstance(navigation.get("label"), str)
                else None,
            )
        )

    diagnostics = safe_response.get("debug")
    safe_state = (
        ConversationState.model_validate(
            _redact_value(conversation_state.model_dump())
        )
        if conversation_state is not None
        else None
    )
    return ChatResponseV1(
        outcome=str(safe_response.get("action", "unknown")),
        message=str(safe_response.get("reply", "")),
        content_blocks=blocks,
        suggested_actions=actions,
        conversation_state=safe_state,
        diagnostics=diagnostics if isinstance(diagnostics, dict) else None,
    )


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value
