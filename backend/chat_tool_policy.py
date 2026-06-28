from __future__ import annotations

from typing import Any, Literal


CHAT_TRAVEL_TOOL_ALLOWLIST = frozenset(
    {
        "get_trips",
        "get_trip",
        "get_trip_timeline",
        "get_experience",
        "get_experience_photos",
        "get_experience_photo_links",
        "get_experience_photo_search",
        "update_experience",
    }
)

CHAT_READ_EXECUTABLE_TOOLS = frozenset(
    {
        "get_trips",
        "get_trip",
        "get_trip_timeline",
        "get_experience",
        "get_experience_photos",
        "get_experience_photo_links",
        "get_experience_photo_search",
    }
)

CHAT_WRITE_PENDING_TOOLS = frozenset({"update_experience"})

ChatToolExecutionPolicy = Literal["read_executable", "write_requires_pending_action"]

CHAT_TOOL_ARGUMENTS: dict[str, frozenset[str]] = {
    "get_trips": frozenset(),
    "get_trip": frozenset({"trip_id"}),
    "get_trip_timeline": frozenset({"trip_id"}),
    "get_experience": frozenset({"experience_id"}),
    "get_experience_photos": frozenset({"experience_id", "limit", "offset"}),
    "get_experience_photo_links": frozenset({"experience_id", "status"}),
    "get_experience_photo_search": frozenset(
        {"experience_id", "from", "to", "limit", "offset"}
    ),
    # Chat v0.1 deliberately exposes only memo updates.
    "update_experience": frozenset({"experience_id", "memo"}),
}

_REQUIRED_ARGUMENTS: dict[str, frozenset[str]] = {
    "get_trips": frozenset(),
    "get_trip": frozenset({"trip_id"}),
    "get_trip_timeline": frozenset({"trip_id"}),
    "get_experience": frozenset({"experience_id"}),
    "get_experience_photos": frozenset({"experience_id"}),
    "get_experience_photo_links": frozenset({"experience_id"}),
    "get_experience_photo_search": frozenset({"experience_id", "from", "to"}),
    "update_experience": frozenset({"experience_id", "memo"}),
}

_PLANNING_FIELDS = frozenset({"goal", "answer_mode", "required_evidence"})
_TOP_LEVEL_FIELDS = frozenset(
    {"action", "tool_id", "arguments", "confidence", "reply", "entity_query"}
) | _PLANNING_FIELDS
_CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})

class ProposalValidationError(ValueError):
    pass


def get_chat_tool_execution_policy(tool_id: str) -> ChatToolExecutionPolicy:
    """Classify a validated Chat tool without consulting untrusted LLM fields."""
    if tool_id in CHAT_READ_EXECUTABLE_TOOLS:
        return "read_executable"
    if tool_id in CHAT_WRITE_PENDING_TOOLS:
        return "write_requires_pending_action"
    raise ProposalValidationError("tool has no chat execution policy")


def validate_chat_proposal(value: Any) -> dict[str, Any]:
    """Validate and normalize untrusted LLM output for Chat v0.1."""
    if not isinstance(value, dict):
        raise ProposalValidationError("proposal must be an object")
    if set(value) - _TOP_LEVEL_FIELDS:
        raise ProposalValidationError("proposal has unsupported fields")

    action = value.get("action")
    reply = value.get("reply")
    if not isinstance(reply, str) or not reply.strip() or len(reply) > 500:
        raise ProposalValidationError("reply must be a non-empty string")

    planning = _validate_planning_fields(value)

    if action == "needs_context":
        if set(value) - ({"action", "reply"} | _PLANNING_FIELDS):
            raise ProposalValidationError("needs_context has unsupported fields")
        return {"action": "needs_context", "reply": reply.strip(), **planning}

    if action != "tool_proposal":
        raise ProposalValidationError("unsupported action")
    required_fields = {"action", "tool_id", "arguments", "confidence", "reply"}
    if not required_fields.issubset(value):
        raise ProposalValidationError("tool_proposal is missing fields")

    tool_id = value.get("tool_id")
    if tool_id not in CHAT_TRAVEL_TOOL_ALLOWLIST:
        raise ProposalValidationError("tool is not allowed")

    confidence = value.get("confidence")
    if confidence not in _CONFIDENCE_VALUES:
        raise ProposalValidationError("unsupported confidence")

    arguments = value.get("arguments")
    if not isinstance(arguments, dict):
        raise ProposalValidationError("arguments must be an object")
    allowed = CHAT_TOOL_ARGUMENTS[tool_id]
    if set(arguments) - allowed:
        raise ProposalValidationError("tool has unsupported arguments")
    if not _REQUIRED_ARGUMENTS[tool_id].issubset(arguments):
        raise ProposalValidationError("tool is missing required arguments")

    normalized_arguments = _validate_argument_values(arguments)
    entity_query = value.get("entity_query")
    if entity_query is not None:
        if tool_id != "get_trips":
            raise ProposalValidationError("entity_query is only valid for get_trips")
        if (
            not isinstance(entity_query, str)
            or not entity_query.strip()
            or len(entity_query) > 256
        ):
            raise ProposalValidationError("entity_query must be a non-empty string")
    return {
        "action": "tool_proposal",
        "tool_id": tool_id,
        "arguments": normalized_arguments,
        "confidence": confidence,
        "reply": reply.strip(),
        "entity_query": entity_query.strip() if entity_query is not None else None,
        **planning,
    }


def _validate_planning_fields(value: dict[str, Any]) -> dict[str, Any]:
    present = _PLANNING_FIELDS.intersection(value)
    if not present:
        # Compatibility for pre-Planner-v2 callers. This is intentionally not
        # semantic classification of the user's words.
        return {"goal": "clarify", "answer_mode": "none", "required_evidence": []}
    if present != _PLANNING_FIELDS:
        raise ProposalValidationError("planning fields must be supplied together")

    goal = value.get("goal")
    answer_mode = value.get("answer_mode")
    evidence = value.get("required_evidence")
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 64:
        raise ProposalValidationError("goal must be a non-empty string")
    if (
        not isinstance(answer_mode, str)
        or not answer_mode.strip()
        or len(answer_mode) > 64
    ):
        raise ProposalValidationError("answer_mode must be a non-empty string")
    if not isinstance(evidence, list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 64
        for item in evidence
    ):
        raise ProposalValidationError("required_evidence must be a string list")
    if len(evidence) > 8 or len(set(evidence)) != len(evidence):
        raise ProposalValidationError("required_evidence is invalid")
    return {
        "goal": goal.strip(),
        "answer_mode": answer_mode.strip(),
        "required_evidence": [item.strip() for item in evidence],
    }


def _validate_argument_values(arguments: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in arguments.items():
        if name in {"trip_id", "experience_id", "from", "to"}:
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ProposalValidationError(f"{name} must be a non-empty string")
            normalized[name] = value.strip()
        elif name == "memo":
            if not isinstance(value, str) or len(value) > 4000:
                raise ProposalValidationError("memo must be a string")
            normalized[name] = value
        elif name == "limit":
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 100
            ):
                raise ProposalValidationError("limit must be between 1 and 100")
            normalized[name] = value
        elif name == "offset":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ProposalValidationError("offset must be zero or greater")
            normalized[name] = value
        elif name == "status":
            if value not in {"active", "archived"}:
                raise ProposalValidationError("status is unsupported")
            normalized[name] = value
        else:  # Defensive: callers must not bypass CHAT_TOOL_ARGUMENTS.
            raise ProposalValidationError("argument is unsupported")
    return normalized
