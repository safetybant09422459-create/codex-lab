from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .activation_rag import activation_search
from .basic_chat import handle_basic_chat
from .chat_core import ConversationTurn
from .chat_orchestrator import handle_travel_chat
from .openai_adapter import generate_text_with_timings, redact_sensitive_text
from .rag_core import RagSearchResult


TimedTextGenerator = Callable[..., tuple[str, dict[str, float] | None]]

_ROUTE_INSTRUCTIONS = """\
Classify one Jarvis conversation turn. Return exactly one JSON object with no
Markdown: {"route":"basic"|"travel","confidence":"high"|"medium"|"low"}.

Choose travel only when answering the current message requires the user's
Travel Skill data or a Travel action, such as listing/opening a saved trip,
recalling a trip/day/experience, or showing photos associated with one.
Choose basic for greetings, thanks, casual conversation, identity/version/time
questions, general knowledge, and anything answerable without Travel Skill data.

Use recent conversation and selected Travel context to understand follow-ups.
Activation candidates are recall hints only. They may help select a Skill, but
they are not verified evidence and never authorize or directly execute a Tool.
Travel is one Skill, not Jarvis's default personality. Infer meaning
semantically; do not classify from a single keyword alone. Do not answer the
question and do not propose or execute a Tool.
"""


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["basic", "travel"]
    confidence: Literal["high", "medium", "low"]


def handle_chat(
    message: str,
    role: str = "admin",
    debug: bool = False,
    context: dict[str, Any] | None = None,
    conversation_history: list[ConversationTurn] | None = None,
    *,
    route_text_generator: TimedTextGenerator | None = None,
    basic_text_generator: TimedTextGenerator | None = None,
    final_answer_text_generator: TimedTextGenerator | None = None,
) -> dict[str, Any]:
    """Select Basic Chat or the existing Travel adapter from validated LLM output."""
    activation_results = _activation_candidates(message, role=role)
    route, route_fallback, route_timings = _select_route(
        message,
        context=context,
        conversation_history=conversation_history,
        activation_results=activation_results,
        text_generator=route_text_generator or generate_text_with_timings,
    )

    if route == "travel":
        result = handle_travel_chat(
            message,
            role=role,
            debug=debug,
            context=context,
            conversation_history=conversation_history,
            final_answer_text_generator=final_answer_text_generator,
        )
        if debug:
            result.setdefault("debug", {})["routing"] = {
                "route": route,
                "fallback": route_fallback,
                "openai_adapter": {"timings_ms": route_timings}
                if route_timings is not None
                else None,
            }
            result["debug"]["activation_results"] = _activation_debug(
                activation_results
            )
            result["debug"]["activation_candidates_present"] = bool(
                activation_results
            )
            result["debug"]["activation_supplied_to_router"] = bool(
                activation_results
            )
        return result

    result = handle_basic_chat(
        message,
        conversation_history=conversation_history,
        text_generator=basic_text_generator,
        debug=debug,
    )
    if debug:
        result.setdefault("debug", {})["routing"] = {
            "route": route,
            "fallback": route_fallback,
            "openai_adapter": {"timings_ms": route_timings}
            if route_timings is not None
            else None,
        }
        result["debug"]["activation_results"] = _activation_debug(
            activation_results
        )
        result["debug"]["activation_candidates_present"] = bool(
            activation_results
        )
        result["debug"]["activation_supplied_to_router"] = bool(
            activation_results
        )
    return result


def _select_route(
    message: str,
    *,
    context: dict[str, Any] | None,
    conversation_history: list[ConversationTurn] | None,
    activation_results: list[RagSearchResult] | None = None,
    text_generator: TimedTextGenerator,
) -> tuple[Literal["basic", "travel"], bool, dict[str, float] | None]:
    safe_history = [
        {"role": turn.role, "content": redact_sensitive_text(turn.content)}
        for turn in (conversation_history or [])
    ]
    # Client context is only a routing hint. Keep only bounded Travel fields;
    # the Travel adapter still revalidates entity state before any execution.
    safe_context = _routing_context(context)
    safe_activation = [
        {
            "source_skill": result.document.source_skill,
            "entity_type": result.document.entity_type,
            "entity_id": result.document.entity_id,
            "text": redact_sensitive_text(result.document.text[:300]),
            "score": result.score,
            "reason": result.reason,
        }
        for result in (activation_results or [])
    ]
    input_text = (
        f"Current message:\n{redact_sensitive_text(message.strip())}\n"
        "Recent conversation (oldest first):\n"
        f"{json.dumps(safe_history, ensure_ascii=False, separators=(',', ':'))}\n"
        "Selected Travel context (unverified hint):\n"
        f"{json.dumps(safe_context, ensure_ascii=False, separators=(',', ':'))}\n"
        "Activation candidates (unverified recall hints):\n"
        f"{json.dumps(safe_activation, ensure_ascii=False, separators=(',', ':'))}"
    )
    timings: dict[str, float] | None = None
    try:
        raw, timings = text_generator(
            instructions=_ROUTE_INSTRUCTIONS,
            input_text=input_text,
        )
        decision = RouteDecision.model_validate(json.loads(raw))
        return decision.route, False, timings
    except Exception:
        # A routing failure must not invoke a Skill or Runtime.
        return "basic", True, timings


def _routing_context(context: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(context, dict):
        return None
    result: dict[str, str] = {}
    for key in ("selected_trip_id", "selected_trip_title"):
        value = context.get(key)
        if isinstance(value, str) and 0 < len(value.strip()) <= 256:
            result[key] = redact_sensitive_text(value.strip())
    return result or None


def _activation_candidates(message: str, *, role: str) -> list[RagSearchResult]:
    visibility_by_role = {
        "admin": None,
        "family": {"family", "shared", "public"},
        "guest": {"shared", "public"},
    }
    try:
        return activation_search(
            message,
            limit=5,
            allowed_visibilities=visibility_by_role.get(role, {"shared", "public"}),
        )
    except Exception:
        # Recall availability must not break Basic Chat or authorize a Skill fallback.
        return []


def _activation_debug(results: list[RagSearchResult]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": result.document.id,
            "source_skill": result.document.source_skill,
            "entity_type": result.document.entity_type,
            "entity_id": result.document.entity_id,
            "visibility": result.document.visibility,
            "score": result.score,
            "matched_terms": result.matched_terms,
            "reason": result.reason,
        }
        for result in results
    ]
