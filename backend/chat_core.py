from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

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


class ConversationState(ChatCoreModel):
    active_skill: str | None = None
    selected_entities: list[EntityRef] = Field(default_factory=list)
    skill_slots: dict[str, Any] = Field(default_factory=dict)


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


class EntityResolver(Protocol):
    """Common future boundary for skill-specific entity candidate discovery."""

    def resolve(
        self,
        query: str,
        *,
        conversation_state: ConversationState,
    ) -> list[EntityCandidate]: ...


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
