from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from time import perf_counter
from typing import Any

from .core_models import ConversationTurn
from .openai_adapter import generate_text_with_timings, redact_sensitive_text


TimedTextGenerator = Callable[..., tuple[str, dict[str, float] | None]]

_INSTRUCTIONS = """\
You are Jarvis, the general-purpose assistant in Jarvis Dev v0.3.
Answer the user's current message naturally and directly in Japanese unless the
user asks for another language. You are in Basic Chat: do not claim to have
called a Skill, Tool, database, external service, or private memory.

Use recent conversation only as ephemeral working context. Do not say that it
was persisted or retrieved from long-term memory. The supplied current local
date/time is authoritative for questions about the current time. Be concise,
helpful, and honest about capabilities. Return plain text only.
"""

_FALLBACK_REPLY = (
    "すみません、今はうまく回答を生成できませんでした。"
    "もう一度お願いします。"
)


def handle_basic_chat(
    message: str,
    *,
    conversation_history: list[ConversationTurn] | None = None,
    text_generator: TimedTextGenerator | None = None,
    now: datetime | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Generate a Tool-free Jarvis response from ephemeral working context."""
    started = perf_counter()
    safe_message = redact_sensitive_text(message.strip())
    safe_history = [
        {
            "role": turn.role,
            "content": redact_sensitive_text(turn.content),
        }
        for turn in (conversation_history or [])
    ]
    current_time = now or datetime.now().astimezone()
    input_text = (
        f"Current local date/time: {current_time.isoformat(timespec='seconds')}\n"
        "Recent conversation (oldest first):\n"
        f"{json.dumps(safe_history, ensure_ascii=False, separators=(',', ':'))}\n"
        f"Current user message:\n{safe_message}"
    )

    adapter_timings: dict[str, float] | None = None
    fallback = False
    try:
        reply, adapter_timings = (text_generator or generate_text_with_timings)(
            instructions=_INSTRUCTIONS,
            input_text=input_text,
        )
        reply = redact_sensitive_text(reply.strip())
        if not reply:
            raise ValueError("Basic Chat returned an empty response")
    except Exception:
        fallback = True
        reply = _FALLBACK_REPLY

    result: dict[str, Any] = {"action": "direct_answer", "reply": reply}
    if debug:
        diagnostics: dict[str, Any] = {
            "route": "basic",
            "fallback": fallback,
            "timings_ms": {"total": _elapsed_ms(started)},
        }
        if adapter_timings is not None:
            diagnostics["openai_adapter"] = {"timings_ms": adapter_timings}
        result["debug"] = diagnostics
    return result


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
