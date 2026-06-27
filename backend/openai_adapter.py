import re
from typing import Any

from .config import OPENAI_API_KEY, OPENAI_MODEL


class OpenAIConfigurationError(RuntimeError):
    pass


def _create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "OpenAI SDK is not installed; run: pip install openai"
        ) from exc

    return OpenAI(api_key=OPENAI_API_KEY)


def check_openai_connection() -> str:
    """Send a minimal server-side request and return text or a safe error."""
    if not OPENAI_API_KEY:
        return "OpenAI connection failed: OPENAI_API_KEY is not configured"
    if not OPENAI_MODEL:
        return "OpenAI connection failed: OPENAI_MODEL is not configured"

    try:
        response = _create_client().responses.create(
            model=OPENAI_MODEL,
            input="Reply with OK only.",
            store=False,
        )
    except Exception as exc:
        return f"OpenAI connection failed: {_safe_exception_message(exc)}"

    try:
        text = _extract_response_text(response)
    except Exception as exc:
        return (
            "OpenAI connection failed: invalid Responses API response: "
            f"{_safe_exception_message(exc)}"
        )
    if text:
        return text

    details = _empty_response_details(response)
    return f"OpenAI connection failed: response contained no text output{details}"


def _extract_response_text(response: Any) -> str:
    """Extract text from a Responses API response without assuming item order."""
    output_text = _get_value(response, "output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: list[str] = []
    for item in _get_value(response, "output") or []:
        for content in _get_value(item, "content") or []:
            if _get_value(content, "type") != "output_text":
                continue
            text = _get_value(content, "text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n".join(texts)


def _empty_response_details(response: Any) -> str:
    details: list[str] = []
    status = _get_value(response, "status")
    if status:
        details.append(f"status={status}")

    incomplete = _get_value(response, "incomplete_details")
    reason = _get_value(incomplete, "reason") if incomplete else None
    if reason:
        details.append(f"reason={reason}")
    return f" ({', '.join(details)})" if details else ""


def _safe_exception_message(exc: Exception) -> str:
    message = _redact_secrets(str(exc).strip() or exc.__class__.__name__)
    return f"{exc.__class__.__name__}: {message}"


def _redact_secrets(message: str) -> str:
    if OPENAI_API_KEY:
        message = message.replace(OPENAI_API_KEY, "[REDACTED]")
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", message)
    return message


def _get_value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
