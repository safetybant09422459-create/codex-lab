import re
from threading import Lock
from time import perf_counter
from typing import Any

from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    OPENAI_VERBOSITY,
)


_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
_VERBOSITY_LEVELS = {"low", "medium", "high"}
_client: Any | None = None
_client_lock = Lock()


class OpenAIConfigurationError(RuntimeError):
    pass


class OpenAIRequestError(RuntimeError):
    def __init__(
        self, message: str, *, timings_ms: dict[str, float] | None = None
    ) -> None:
        super().__init__(message)
        self.timings_ms = dict(timings_ms) if timings_ms is not None else None


def _create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "OpenAI SDK is not installed; run: pip install openai"
        ) from exc

    return OpenAI(api_key=OPENAI_API_KEY)


def _get_client() -> Any:
    """Return one client per process so its HTTP connection pool is reused."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _create_client()
    return _client


def generate_text(*, instructions: str, input_text: str) -> str:
    """Generate server-side text without storing the OpenAI response."""
    text, _timings_ms = generate_text_with_timings(
        instructions=instructions,
        input_text=input_text,
    )
    return text


def generate_text_with_timings(
    *, instructions: str, input_text: str
) -> tuple[str, dict[str, float]]:
    """Generate text and return safe, aggregate adapter timings in milliseconds."""
    started = perf_counter()
    timings_ms = {
        "api_call": 0.0,
        "response_text_extraction": 0.0,
        "total": 0.0,
    }
    if not OPENAI_API_KEY:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured")
    if not OPENAI_MODEL:
        raise OpenAIConfigurationError("OPENAI_MODEL is not configured")

    try:
        api_started = perf_counter()
        try:
            request = {
                "model": OPENAI_MODEL,
                "instructions": instructions,
                "input": input_text,
                "store": False,
            }
            request.update(_inference_settings())
            response = _get_client().responses.create(**request)
        finally:
            timings_ms["api_call"] = _elapsed_ms(api_started)

        extraction_started = perf_counter()
        try:
            text = _extract_response_text(response)
        finally:
            timings_ms["response_text_extraction"] = _elapsed_ms(
                extraction_started
            )
    except Exception as exc:
        timings_ms["total"] = _elapsed_ms(started)
        raise OpenAIRequestError(
            _safe_exception_message(exc), timings_ms=timings_ms
        ) from None
    finally:
        timings_ms["total"] = _elapsed_ms(started)

    if not text:
        raise OpenAIRequestError("OpenAI response contained no text output")
    return text, timings_ms


def check_openai_connection() -> str:
    """Send a minimal server-side request and return text or a safe error."""
    if not OPENAI_API_KEY:
        return "OpenAI connection failed: OPENAI_API_KEY is not configured"
    if not OPENAI_MODEL:
        return "OpenAI connection failed: OPENAI_MODEL is not configured"

    try:
        response = _get_client().responses.create(
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


def _inference_settings() -> dict[str, Any]:
    """Build optional Responses API inference settings from server config."""
    settings: dict[str, Any] = {}

    if OPENAI_REASONING_EFFORT:
        if OPENAI_REASONING_EFFORT not in _REASONING_EFFORTS:
            raise OpenAIConfigurationError(
                "OPENAI_REASONING_EFFORT must be one of: "
                + ", ".join(sorted(_REASONING_EFFORTS))
            )
        settings["reasoning"] = {"effort": OPENAI_REASONING_EFFORT}

    if OPENAI_VERBOSITY:
        if OPENAI_VERBOSITY not in _VERBOSITY_LEVELS:
            raise OpenAIConfigurationError(
                "OPENAI_VERBOSITY must be one of: "
                + ", ".join(sorted(_VERBOSITY_LEVELS))
            )
        settings["text"] = {"verbosity": OPENAI_VERBOSITY}

    try:
        max_output_tokens = int(OPENAI_MAX_OUTPUT_TOKENS)
    except ValueError:
        raise OpenAIConfigurationError(
            "OPENAI_MAX_OUTPUT_TOKENS must be a positive integer"
        ) from None
    if max_output_tokens <= 0:
        raise OpenAIConfigurationError(
            "OPENAI_MAX_OUTPUT_TOKENS must be a positive integer"
        )
    settings["max_output_tokens"] = max_output_tokens
    return settings


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
    message = re.sub(r"(?i)bearer\s+\S+", "[REDACTED]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", message)
    return message


def redact_sensitive_text(message: str) -> str:
    """Redact configured OpenAI credentials and bearer tokens from text."""
    return _redact_secrets(message)


def _get_value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
