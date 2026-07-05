from __future__ import annotations

import json
from collections.abc import Callable
from time import perf_counter
from typing import Any

from .chat_core import (
    ConversationState,
    ConversationWorkingContext,
    Plan,
    PlanToolCandidate,
)
from .chat_tool_policy import (
    CHAT_TOOL_ARGUMENTS,
    CHAT_TRAVEL_TOOL_ALLOWLIST,
    CHAT_WRITE_PENDING_TOOLS,
    validate_chat_proposal,
)
from .openai_adapter import (
    OpenAIRequestError,
    generate_text_with_timings,
    redact_sensitive_text,
)
from .travel_chat_adapter import conversation_state_from_legacy_context


TimedTextGenerator = Callable[..., tuple[str, dict[str, float] | None]]


_FALLBACK_REASON = (
    "Toolを安全に提案できませんでした。"
    "対象の旅行または体験をもう少し具体的に指定してください。"
)

_TARGET_ENTITY_TYPES = {
    "get_trips": "trip",
    "get_trip": "trip",
    "get_trip_timeline": "trip",
    "get_experience": "experience",
    "get_experience_photos": "experience",
    "get_experience_photo_links": "experience",
    "get_experience_photo_search": "experience",
    "update_experience": "experience",
}

_GOAL_CONTRACT = {
    "open_trip": ("none", ("trip",)),
    "summarize_trip": ("summary", ("trip", "timeline")),
    "summarize_day": ("day_summary", ("trip", "timeline")),
    "summarize_meals": ("meals", ("trip", "timeline")),
    "show_photos": ("photos", ("trip", "experience", "photo")),
    "clarify": ("clarification", ()),
}

_INSTRUCTIONS = """\
You are the proposal-only Planner for Jarvis Travel Chat v0.1.
Return exactly one JSON object and no Markdown or commentary.
You propose a tool; you never execute it.

Allowed actions:
- tool_proposal: action, goal, answer_mode, required_evidence, tool_id,
  arguments, optional entity_query, confidence, reply
- needs_context: action, goal, answer_mode, required_evidence, reply

Allowed goal contracts (use exactly one):
- open_trip: answer_mode=none, required_evidence=["trip"]
- summarize_trip: answer_mode=summary, required_evidence=["trip","timeline"]
- summarize_day: answer_mode=day_summary, required_evidence=["trip","timeline"]
- summarize_meals: answer_mode=meals, required_evidence=["trip","timeline"]
- show_photos: answer_mode=photos, required_evidence=["trip","experience","photo"]
- clarify: answer_mode=clarification, required_evidence=[]

Allowed tool IDs and arguments:
{tool_policy}

Rules:
- Interpret the current question first. Conversation history is supporting working
  context, and ConversationState is a weaker read-only hint. An explicitly named
  subject in the current question replaces a different subject in either context.
- Never invent or decide role, confirmed, user_id, permission, or authorization.
- ConversationState may include a selected trip EntityRef. Use its entity_id for
  references to that selected trip, but never return or update state yourself.
- Use only an allowed tool and only its listed arguments.
- A trip title, area, prefecture, or memo keyword is not a trip_id. To find a
  matching trip, propose get_trips with empty arguments and put only the subject
  to resolve in entity_query. Omit entity_query when listing all trips.
- Questions asking what someone did or ate on a named trip also use get_trips;
  the Executor resolves the trip and obtains its existing timeline Evidence.
- With selected_trip_id, questions asking what happened, what was eaten, or what
  happened on a numbered day use get_trip_timeline.
- A place or experience name is not an experience_id. If photos or details need an
  experience_id and no actual ID is available, return needs_context.
- update_experience is proposal-only and accepts exactly experience_id and memo.
- Do not request or return photo binary data.
- Infer goal semantically. Do not rely on a fixed keyword or phrase match.
- goal describes the user's desired result, not merely the first Tool call.
- confidence must be high, medium, or low.
- reply must be concise Japanese suitable for the user.

Examples:
User: 旅行一覧を見せて
{{"action":"tool_proposal","goal":"open_trip","answer_mode":"none","required_evidence":["trip"],"tool_id":"get_trips","arguments":{{}},"confidence":"high","reply":"旅行一覧を取得します。"}}
User: 福岡旅行を開いて
{{"action":"tool_proposal","goal":"open_trip","answer_mode":"none","required_evidence":["trip"],"tool_id":"get_trips","arguments":{{}},"entity_query":"福岡旅行","confidence":"medium","reply":"福岡旅行を探します。"}}
User: 神戸旅行で何した？
{{"action":"tool_proposal","goal":"summarize_trip","answer_mode":"summary","required_evidence":["trip","timeline"],"tool_id":"get_trips","arguments":{{}},"entity_query":"神戸旅行","confidence":"medium","reply":"神戸旅行を探します。"}}
User: 須磨を開いて
{{"action":"tool_proposal","goal":"open_trip","answer_mode":"none","required_evidence":["trip"],"tool_id":"get_trips","arguments":{{}},"entity_query":"須磨","confidence":"medium","reply":"須磨に合う旅行を探します。"}}
User: 兵庫の旅行見せて
{{"action":"tool_proposal","goal":"open_trip","answer_mode":"none","required_evidence":["trip"],"tool_id":"get_trips","arguments":{{}},"entity_query":"兵庫","confidence":"medium","reply":"兵庫に合う旅行を探します。"}}
User: 旅行を開いて
{{"action":"tool_proposal","goal":"clarify","answer_mode":"clarification","required_evidence":[],"tool_id":"get_trips","arguments":{{}},"confidence":"medium","reply":"候補を確認します。"}}
Context: selected_trip_id=trip_fukuoka, selected_trip_title=福岡旅行
User: この旅行の詳細見せて
{{"action":"tool_proposal","goal":"open_trip","answer_mode":"none","required_evidence":["trip"],"tool_id":"get_trip","arguments":{{"trip_id":"trip_fukuoka"}},"confidence":"high","reply":"選択中の旅行を取得します。"}}
Context: selected_trip_id=trip_fukuoka, selected_trip_title=福岡旅行
User: 2日目は？
{{"action":"tool_proposal","goal":"summarize_day","answer_mode":"day_summary","required_evidence":["trip","timeline"],"tool_id":"get_trip_timeline","arguments":{{"trip_id":"trip_fukuoka"}},"confidence":"high","reply":"選択中の旅行の日程を取得します。"}}
Context: selected_trip_id=trip_fukuoka, selected_trip_title=福岡旅行
User: 何食べた？
{{"action":"tool_proposal","goal":"summarize_meals","answer_mode":"meals","required_evidence":["trip","timeline"],"tool_id":"get_trip_timeline","arguments":{{"trip_id":"trip_fukuoka"}},"confidence":"high","reply":"選択中の旅行の日程を取得します。"}}
User: アンパンマンミュージアムの写真見せて
{{"action":"needs_context","goal":"show_photos","answer_mode":"photos","required_evidence":["trip","experience","photo"],"reply":"アンパンマンミュージアムの写真を探すには、対象体験の写真連携が必要です。"}}
""".format(
    tool_policy=json.dumps(
        {
            tool_id: sorted(CHAT_TOOL_ARGUMENTS[tool_id])
            for tool_id in sorted(CHAT_TRAVEL_TOOL_ALLOWLIST)
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
)


class TravelPlanner:
    """Convert a validated Travel LLM proposal into a descriptive Plan only."""

    planner_id = "travel_planner"

    def __init__(
        self,
        *,
        timed_text_generator: TimedTextGenerator = generate_text_with_timings,
    ) -> None:
        self._timed_text_generator = timed_text_generator

    def create_plan(
        self,
        user_message: str,
        *,
        conversation: ConversationWorkingContext | None = None,
        conversation_state: ConversationState | None = None,
        context: dict[str, Any] | None = None,
        text_generator: Callable[..., str] | None = None,
        debug: bool = False,
    ) -> Plan:
        total_started = perf_counter()
        timings_ms = {
            "build_prompt": 0.0,
            "llm_call": 0.0,
            "json_parse": 0.0,
            "policy_validation": 0.0,
            "fallback": 0.0,
            "total": 0.0,
        }
        adapter_timings_ms: dict[str, float] | None = None

        try:
            prompt_started = perf_counter()
            try:
                if not isinstance(user_message, str) or not user_message.strip():
                    raise ValueError("user message must be a non-empty string")
                safe_message = redact_sensitive_text(user_message.strip())
                state = conversation_state or conversation_state_from_legacy_context(
                    context
                )
                safe_history = _redact_value(
                    (conversation or ConversationWorkingContext()).model_dump()["turns"]
                )
                safe_state = _redact_value(state.model_dump(mode="json"))
                history_text = json.dumps(
                    safe_history,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                state_text = json.dumps(
                    safe_state,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                input_text = (
                    f"Current question:\n{safe_message}\n"
                    "Conversation history (ephemeral working context, oldest first):\n"
                    f"{history_text}\n"
                    "ConversationState (read-only state hint):\n"
                    f"{state_text}"
                )
            finally:
                timings_ms["build_prompt"] = _elapsed_ms(prompt_started)

            llm_started = perf_counter()
            try:
                if text_generator is None:
                    raw_response, adapter_timings_ms = self._timed_text_generator(
                        instructions=_INSTRUCTIONS,
                        input_text=input_text,
                    )
                else:
                    raw_response = text_generator(
                        instructions=_INSTRUCTIONS,
                        input_text=input_text,
                    )
            finally:
                timings_ms["llm_call"] = _elapsed_ms(llm_started)

            parse_started = perf_counter()
            try:
                parsed = json.loads(raw_response)
            finally:
                timings_ms["json_parse"] = _elapsed_ms(parse_started)

            validation_started = perf_counter()
            try:
                proposal = validate_chat_proposal(parsed)
            finally:
                timings_ms["policy_validation"] = _elapsed_ms(validation_started)

            plan = self._proposal_to_plan(
                _normalize_goal_contract(_redact_value(proposal))
            )
        except Exception as exc:
            if isinstance(exc, OpenAIRequestError) and exc.timings_ms is not None:
                adapter_timings_ms = exc.timings_ms
            fallback_started = perf_counter()
            try:
                plan = self._fallback_plan()
            finally:
                timings_ms["fallback"] = _elapsed_ms(fallback_started)

        timings_ms["total"] = _elapsed_ms(total_started)
        if not debug:
            return plan

        diagnostics: dict[str, Any] = {
            "planner": self.planner_id,
            "timings_ms": timings_ms,
        }
        if adapter_timings_ms is not None:
            diagnostics["openai_adapter"] = {"timings_ms": adapter_timings_ms}
        return plan.model_copy(update={"diagnostics": diagnostics})

    @staticmethod
    def _proposal_to_plan(
        proposal: dict[str, Any],
    ) -> Plan:
        # `reason` carries the validated legacy proposal text for compatibility;
        # the Planner does not compose a new user response.
        if proposal["action"] == "needs_context":
            return Plan(
                intent="needs_context",
                goal=proposal["goal"],
                answer_mode=proposal["answer_mode"],
                required_evidence=proposal["required_evidence"],
                target_skill="travel",
                requires_context=True,
                reason=proposal["reply"],
            )

        tool_id = proposal["tool_id"]
        return Plan(
            intent=tool_id,
            goal=proposal["goal"],
            answer_mode=proposal["answer_mode"],
            required_evidence=proposal["required_evidence"],
            target_skill="travel",
            target_entity_type=_TARGET_ENTITY_TYPES.get(tool_id),
            resolution_query=proposal.get("entity_query"),
            tool_candidates=[
                PlanToolCandidate(
                    tool_id=tool_id,
                    arguments=proposal["arguments"],
                )
            ],
            requires_confirmation=tool_id in CHAT_WRITE_PENDING_TOOLS,
            reason=proposal["reply"],
            confidence=proposal["confidence"],
        )

    @staticmethod
    def _fallback_plan() -> Plan:
        return Plan(
            intent="needs_context",
            target_skill="travel",
            requires_context=True,
            reason=_FALLBACK_REASON,
        )


def legacy_proposal_from_plan(plan: Plan, *, debug: bool = False) -> dict[str, Any]:
    """Adapt a Plan to the existing proposal contract during API migration."""
    if plan.requires_context or not plan.tool_candidates:
        proposal: dict[str, Any] = {
            "action": "needs_context",
            "reply": plan.reason or _FALLBACK_REASON,
        }
    else:
        candidate = plan.tool_candidates[0]
        proposal = {
            "action": "tool_proposal",
            "tool_id": candidate.tool_id,
            "arguments": _redact_value(candidate.arguments),
            "confidence": plan.confidence or "low",
            "reply": plan.reason or _FALLBACK_REASON,
        }

    if debug and plan.diagnostics is not None:
        proposal["debug"] = {
            key: value
            for key, value in plan.diagnostics.items()
            if key != "planner"
        }
    return proposal


def _normalize_goal_contract(proposal: dict[str, Any]) -> dict[str, Any]:
    """Allow only Travel's declared goal tuple; never infer it from user text."""
    goal = proposal.get("goal")
    contract = _GOAL_CONTRACT.get(goal)
    if contract is None:
        raise ValueError("unsupported Travel goal")
    expected_mode, expected_evidence = contract
    if proposal.get("answer_mode") != expected_mode:
        raise ValueError("answer_mode does not match Travel goal")
    if tuple(proposal.get("required_evidence", ())) != expected_evidence:
        raise ValueError("required_evidence does not match Travel goal")
    return proposal


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
