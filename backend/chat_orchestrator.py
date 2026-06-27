from __future__ import annotations

import json
from collections.abc import Callable
from time import perf_counter
from typing import Any

from .chat_tool_policy import (
    CHAT_TOOL_ARGUMENTS,
    CHAT_TRAVEL_TOOL_ALLOWLIST,
    validate_chat_proposal,
)
from .openai_adapter import (
    OpenAIRequestError,
    generate_text_with_timings,
    redact_sensitive_text,
)


_FALLBACK = {
    "action": "needs_context",
    "reply": "Toolを安全に提案できませんでした。対象の旅行または体験をもう少し具体的に指定してください。",
}

_INSTRUCTIONS = """\
You are the proposal-only Chat Orchestrator for Jarvis Travel Chat v0.1.
Return exactly one JSON object and no Markdown or commentary.
You propose a tool; you never execute it.

Allowed actions:
- tool_proposal: action, tool_id, arguments, confidence, reply
- needs_context: action, reply

Allowed tool IDs and arguments:
{tool_policy}

Rules:
- Never invent or decide role, confirmed, user_id, permission, or authorization.
- Use only an allowed tool and only its listed arguments.
- A trip name is not a trip_id. To find a named trip, propose get_trips with empty arguments.
- A place or experience name is not an experience_id. If photos or details need an
  experience_id and no actual ID is available, return needs_context.
- update_experience is proposal-only and accepts exactly experience_id and memo.
- Do not request or return photo binary data.
- confidence must be high, medium, or low.
- reply must be concise Japanese suitable for the user.

Examples:
User: 旅行一覧を見せて
{{"action":"tool_proposal","tool_id":"get_trips","arguments":{{}},"confidence":"high","reply":"旅行一覧を取得します。"}}
User: 福岡旅行を開いて
{{"action":"tool_proposal","tool_id":"get_trips","arguments":{{}},"confidence":"medium","reply":"福岡旅行を探します。"}}
User: アンパンマンミュージアムの写真見せて
{{"action":"needs_context","reply":"どの旅行の体験か確認するため、旅行または体験を先に選んでください。"}}
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


def propose_travel_tool(
    user_message: str,
    *,
    text_generator: Callable[..., str] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Return a validated Travel Tool proposal without executing Runtime or a Tool."""
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
            input_text = f"User utterance:\n{safe_message}"
        finally:
            timings_ms["build_prompt"] = _elapsed_ms(prompt_started)

        llm_started = perf_counter()
        try:
            if text_generator is None:
                raw_response, adapter_timings_ms = generate_text_with_timings(
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

        result = _redact_proposal(proposal)
    except Exception as exc:
        if isinstance(exc, OpenAIRequestError) and exc.timings_ms is not None:
            adapter_timings_ms = exc.timings_ms
        # No raw model output or exception detail is returned or audited here.
        fallback_started = perf_counter()
        try:
            result = dict(_FALLBACK)
        finally:
            timings_ms["fallback"] = _elapsed_ms(fallback_started)

    timings_ms["total"] = _elapsed_ms(total_started)
    if debug:
        result["debug"] = {"timings_ms": timings_ms}
        if adapter_timings_ms is not None:
            result["debug"]["openai_adapter"] = {
                "timings_ms": adapter_timings_ms
            }
    return result


def _redact_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    def redact(value: Any) -> Any:
        if isinstance(value, str):
            return redact_sensitive_text(value)
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return redact(proposal)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
