from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .chat_core import (
    ChatResponseV1,
    ContentBlock,
    ConversationState,
    EntityRef,
    legacy_chat_response_to_v1,
)


TRAVEL_SKILL_ID = "travel"
TRIP_ENTITY_TYPE = "trip"
CLIENT_CONTEXT_SOURCE = "client_context_hint"
RUNTIME_SOURCE = "travel_runtime"


def conversation_state_from_legacy_context(context: Any) -> ConversationState:
    """Convert bounded legacy context into an explicitly unverified state hint.

    Browser-supplied context is not proof that an entity exists or that the caller
    may access it. The orchestrator must retain the current Runtime lookup before
    relying on this entity for a follow-up operation.
    """
    state = ConversationState(active_skill=TRAVEL_SKILL_ID)
    if not isinstance(context, dict):
        return state
    trip_id = context.get("selected_trip_id")
    if not isinstance(trip_id, str) or not trip_id.strip() or len(trip_id) > 256:
        return state
    title = context.get("selected_trip_title")
    label = (
        title.strip()
        if isinstance(title, str) and title.strip() and len(title) <= 500
        else trip_id.strip()
    )
    state.selected_entities.append(
        trip_entity_ref(
            trip_id.strip(),
            label=label,
            source=CLIENT_CONTEXT_SOURCE,
        )
    )
    if isinstance(title, str) and title.strip() and len(title) <= 500:
        state.skill_slots[TRAVEL_SKILL_ID] = {
            "selected_trip_title": title.strip()
        }
    return state


def conversation_state_from_runtime_trip(trip: dict[str, Any]) -> ConversationState:
    trip_id = trip.get("id")
    if not isinstance(trip_id, str) or not trip_id.strip():
        return ConversationState(active_skill=TRAVEL_SKILL_ID)
    title = trip.get("title")
    label = title.strip() if isinstance(title, str) and title.strip() else trip_id.strip()
    skill_slots = {}
    if isinstance(title, str) and title.strip():
        skill_slots[TRAVEL_SKILL_ID] = {"selected_trip_title": title.strip()}
    return ConversationState(
        active_skill=TRAVEL_SKILL_ID,
        selected_entities=[
            trip_entity_ref(
                trip_id.strip(),
                label=label,
                source=RUNTIME_SOURCE,
                verified_at=datetime.now(timezone.utc),
            )
        ],
        skill_slots=skill_slots,
    )


def legacy_context_from_conversation_state(
    state: ConversationState,
) -> dict[str, str]:
    entity = selected_trip_entity(state)
    if entity is None:
        return {}
    context = {"selected_trip_id": entity.entity_id}
    travel_slots = state.skill_slots.get(TRAVEL_SKILL_ID)
    if isinstance(travel_slots, dict):
        title = travel_slots.get("selected_trip_title")
        if isinstance(title, str) and title:
            context["selected_trip_title"] = title
    return context


def selected_trip_entity(state: ConversationState) -> EntityRef | None:
    for entity in state.selected_entities:
        if entity.skill_id == TRAVEL_SKILL_ID and entity.entity_type == TRIP_ENTITY_TYPE:
            return entity
    return None


def trip_entity_ref(
    trip_id: str,
    *,
    label: str,
    source: str,
    verified_at: datetime | None = None,
) -> EntityRef:
    return EntityRef(
        skill_id=TRAVEL_SKILL_ID,
        entity_type=TRIP_ENTITY_TYPE,
        entity_id=trip_id,
        label=label,
        source=source,
        verified_at=verified_at,
    )


def travel_content_blocks(response: dict[str, Any]) -> list[ContentBlock]:
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    tool_id = response.get("tool_id")
    block_type = {
        "get_trips": "travel_trip_list",
        "get_trip": "travel_trip",
        "get_trip_timeline": "travel_timeline",
    }.get(tool_id, "travel_tool_result")
    return [ContentBlock(type=block_type, data=result)]


def compose_travel_chat_response_v1(
    response: dict[str, Any],
    *,
    conversation_state: ConversationState | None = None,
) -> ChatResponseV1:
    return legacy_chat_response_to_v1(
        response,
        conversation_state=conversation_state,
        content_blocks=travel_content_blocks(response),
    )
