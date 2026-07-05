import json
import re
from threading import Lock
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from .agent_host import ACTION_ADAPTER, LLMInputPayload
from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    OPENAI_TIMEOUT_SECONDS,
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


class OpenAIResponseValidationError(OpenAIRequestError):
    """Raised when structured model output is not a valid LLM Action."""


class OpenAITimeoutError(OpenAIRequestError):
    """Raised when the AI model provider request exceeds its timeout."""


class OpenAIModelRefusalError(OpenAIRequestError):
    """Raised when the provider refuses to produce the structured output."""


class OpenAIIncompleteResponseError(OpenAIRequestError):
    """Raised when the provider reports an incomplete response."""


class OpenAIModelProviderAdapter:
    """OpenAI Responses API implementation of the provider-neutral LLMClient."""

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]:
        _validate_configuration()
        request = _build_action_request(payload)
        try:
            response = _get_client().responses.create(**request)
        except Exception as exc:
            if _is_timeout_exception(exc):
                raise OpenAITimeoutError(_safe_exception_message(exc)) from None
            raise OpenAIRequestError(_safe_exception_message(exc)) from None

        _raise_for_unsuccessful_action_response(response)
        try:
            structured_output = json.loads(_extract_response_text(response))
            raw_action = structured_output["llm_action"]
            action = ACTION_ADAPTER.validate_python(raw_action)
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise OpenAIResponseValidationError(
                f"OpenAI returned an invalid LLM Action: {_safe_exception_message(exc)}"
            ) from None
        return action.model_dump(mode="json")


# Explicit generic name for configuration code that selects this provider.
AIModelProviderAdapter = OpenAIModelProviderAdapter


def _create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "OpenAI SDK is not installed; run: pip install openai"
        ) from exc

    return OpenAI(api_key=OPENAI_API_KEY, timeout=_timeout_seconds())


def _timeout_seconds() -> float:
    try:
        timeout = float(OPENAI_TIMEOUT_SECONDS)
    except ValueError:
        raise OpenAIConfigurationError(
            "OPENAI_TIMEOUT_SECONDS must be a positive number"
        ) from None
    if timeout <= 0:
        raise OpenAIConfigurationError(
            "OPENAI_TIMEOUT_SECONDS must be a positive number"
        )
    return timeout


def _validate_configuration() -> None:
    if not OPENAI_API_KEY:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured")
    if not OPENAI_MODEL:
        raise OpenAIConfigurationError("OPENAI_MODEL is not configured")
    _timeout_seconds()


def _build_action_request(payload: LLMInputPayload) -> dict[str, Any]:
    inference_settings = _inference_settings()
    text_settings = dict(inference_settings.pop("text", {}))
    text_settings["format"] = {
        "type": "json_schema",
        "name": "jarvis_llm_action_v1",
        "strict": True,
        "schema": _action_output_schema(),
    }
    request = {
        "model": OPENAI_MODEL,
        "instructions": (
            "Return exactly one Jarvis LLM Action matching the supplied JSON "
            "schema. Use only the supplied context and operation catalog. "
            "Select call_operation when an available operation is needed to "
            "answer the user. After a prior observation, use that observation "
            "to return a terminal action and do not call another operation. "
            "Do not include reasoning, analysis, or hidden thought."
        ),
        "input": json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
        "store": False,
        "text": text_settings,
    }
    request.update(inference_settings)
    return request


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Apply the Responses API strict-schema requirement mechanically."""
    schema = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "oneOf" in node:
                node["anyOf"] = node.pop("oneOf")
            node.pop("discriminator", None)
            if node.get("type") == "object":
                properties = node.get("properties")
                if not isinstance(properties, dict):
                    properties = {}
                    node["properties"] = properties
                node["additionalProperties"] = False
                node["required"] = list(properties)
            node.pop("default", None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema


def _inline_local_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Expand local JSON pointers before nesting the schema in an API envelope."""
    root = json.loads(json.dumps(schema))

    def resolve_pointer(reference: str) -> Any:
        if not reference.startswith("#/"):
            raise ValueError(f"Unsupported JSON Schema reference: {reference}")
        target: Any = root
        for raw_part in reference[2:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                raise ValueError(f"Unresolved JSON Schema reference: {reference}")
            target = target[part]
        return target

    def expand(node: Any, resolving: tuple[str, ...] = ()) -> Any:
        if isinstance(node, list):
            return [expand(item, resolving) for item in node]
        if not isinstance(node, dict):
            return node

        reference = node.get("$ref")
        if reference is not None:
            if not isinstance(reference, str):
                raise ValueError("JSON Schema $ref must be a string")
            if reference in resolving:
                raise ValueError(f"Circular JSON Schema reference: {reference}")
            expanded = expand(
                json.loads(json.dumps(resolve_pointer(reference))),
                (*resolving, reference),
            )
            if not isinstance(expanded, dict):
                raise ValueError(f"JSON Schema reference is not an object: {reference}")
            siblings = {
                key: expand(value, resolving)
                for key, value in node.items()
                if key != "$ref"
            }
            expanded.update(siblings)
            return expanded

        return {
            key: expand(value, resolving)
            for key, value in node.items()
            if key not in {"$defs", "definitions"}
        }

    expanded = expand(root)
    if not isinstance(expanded, dict):
        raise ValueError("Expanded JSON Schema root must be an object")
    return expanded


def _action_output_schema() -> dict[str, Any]:
    """Wrap the discriminated union because strict output requires a root object."""
    action_schema = _strict_json_schema(
        _inline_local_refs(ACTION_ADAPTER.json_schema())
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"llm_action": action_schema},
        "required": ["llm_action"],
    }


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
    _validate_configuration()

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


def _raise_for_unsuccessful_action_response(response: Any) -> None:
    status = _get_value(response, "status")
    if status == "incomplete":
        details = _empty_response_details(response)
        raise OpenAIIncompleteResponseError(
            "OpenAI returned an incomplete response" + details
        )

    for item in _get_value(response, "output") or []:
        for content in _get_value(item, "content") or []:
            if _get_value(content, "type") == "refusal":
                raise OpenAIModelRefusalError("OpenAI model refused the request")


def _is_timeout_exception(exc: Exception) -> bool:
    return isinstance(exc, TimeoutError) or exc.__class__.__name__ in {
        "APITimeoutError",
        "ConnectTimeout",
        "ReadTimeout",
        "TimeoutException",
    }


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
