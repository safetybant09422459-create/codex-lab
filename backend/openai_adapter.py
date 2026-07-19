import json
import re
from copy import deepcopy
from threading import Lock
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from .agent_host import ACTION_ADAPTER, LLMInputPayload
from .chat_trace import ChatTraceRecorder, extract_usage, sanitize, utc_now
from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    OPENAI_TIMEOUT_SECONDS,
    OPENAI_VERBOSITY,
)
from .native_tools import (
    NativeToolArgumentsError,
    NativeToolRegistry,
    NativeToolSchemaError,
    compile_registry,
    normalize_arguments,
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

    def __init__(self, trace_recorder: ChatTraceRecorder | None = None) -> None:
        self.trace_recorder = trace_recorder

    def complete(self, payload: LLMInputPayload) -> dict[str, Any]:
        step = 2 if payload.prior_observations else 1
        started_at = utc_now()
        started = perf_counter()
        request: dict[str, Any] | None = None
        response: Any = None
        try:
            _validate_configuration()
            request, registry = _build_action_request_with_registry(payload)
            try:
                response = _get_client().responses.create(**request)
            except Exception as exc:
                if _is_timeout_exception(exc):
                    raise OpenAITimeoutError(_safe_exception_message(exc)) from None
                raise OpenAIRequestError(_safe_exception_message(exc)) from None

            _raise_for_unsuccessful_action_response(response)
            action = ACTION_ADAPTER.validate_python(
                _normalize_native_tool_response(response, registry)
            )
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
        ) as exc:
            error = OpenAIResponseValidationError(
                f"OpenAI returned an invalid LLM Action: {_safe_exception_message(exc)}"
            )
            self._record_trace(payload, step, started_at, started, request, response, error=error)
            raise error from None
        except Exception as exc:
            self._record_trace(payload, step, started_at, started, request, response, error=exc)
            raise
        normalized = action.model_dump(mode="json")
        self._record_trace(payload, step, started_at, started, request, response, action=normalized)
        return normalized

    def _record_trace(
        self, payload: LLMInputPayload, step: int, started_at: str,
        started: float, request: dict[str, Any] | None, response: Any,
        *, action: dict[str, Any] | None = None, error: Exception | None = None,
    ) -> None:
        if self.trace_recorder is None:
            return
        category = _trace_error_category(error) if error else None
        tools = (request or {}).get("tools", [])
        function_calls = [
            item for item in (_get_value(response, "output") or [])
            if _get_value(item, "type") == "function_call"
        ]
        control_count = sum(
            1 for tool in tools if str(tool.get("name", "")).startswith("jarvis_control_")
        )
        request_input_payload: dict[str, Any] = {}
        raw_request_input = (request or {}).get("input")
        if isinstance(raw_request_input, str):
            try:
                decoded_input = json.loads(raw_request_input)
                if isinstance(decoded_input, dict):
                    request_input_payload = decoded_input
            except json.JSONDecodeError:
                pass
        request_operations = request_input_payload.get("available_operations")
        self.trace_recorder.record_llm_call(payload.turn_id, {
            "step": step,
            "request": {
                "model": (request or {}).get("model", OPENAI_MODEL),
                "reasoning_effort": OPENAI_REASONING_EFFORT or None,
                "verbosity": OPENAI_VERBOSITY or None,
                "max_output_tokens": (request or {}).get("max_output_tokens"),
                "timeout_seconds": _safe_timeout_value(),
                "store": (request or {}).get("store"),
                "tool_choice": (request or {}).get("tool_choice"),
                "tool_names": [tool.get("name") for tool in tools],
                "operation_tool_count": len(tools) - control_count,
                "control_tool_count": control_count,
                "instructions": (request or {}).get("instructions"),
                "llm_input_payload": request_input_payload,
                "operation_catalog_present": "available_operations" in request_input_payload,
                "input_payload_bytes": len(raw_request_input.encode("utf-8"))
                if isinstance(raw_request_input, str) else 0,
                "available_operations_bytes": len(json.dumps(
                    request_operations, ensure_ascii=False
                ).encode("utf-8")) if request_operations is not None else 0,
                "tool_definitions": tools,
                "started_at": started_at,
                "completed_at": utc_now(),
            },
            "response": {
                "response_id": _get_value(response, "id"),
                "status": _get_value(response, "status"),
                "incomplete_details": _get_value(response, "incomplete_details"),
                "refusal": any(
                    _get_value(content, "type") == "refusal"
                    for item in (_get_value(response, "output") or [])
                    for content in (_get_value(item, "content") or [])
                ),
                "function_call_count": len(function_calls),
                "function_call_names": [_get_value(call, "name") for call in function_calls],
                "raw_arguments": [_get_value(call, "arguments") for call in function_calls],
                "normalized_action": action,
                "validation_error": sanitize(error) if isinstance(error, OpenAIResponseValidationError) else None,
            },
            "usage": extract_usage(response),
            "error_category": category,
            "error_message": sanitize(error) if error else None,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
        })


def _trace_error_category(error: Exception | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, OpenAIConfigurationError):
        return "configuration_error"
    if isinstance(error, OpenAITimeoutError):
        return "timeout"
    if isinstance(error, OpenAIModelRefusalError):
        return "provider_refusal"
    if isinstance(error, OpenAIIncompleteResponseError):
        return "provider_incomplete"
    if isinstance(error, OpenAIResponseValidationError):
        return "malformed_response"
    if isinstance(error, OpenAIRequestError):
        return "provider_request_error"
    return "internal_error"


def _safe_timeout_value() -> float | None:
    try:
        return float(OPENAI_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return None


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
    request, _registry = _build_action_request_with_registry(payload)
    return request


def _build_action_request_with_registry(
    payload: LLMInputPayload,
) -> tuple[dict[str, Any], NativeToolRegistry]:
    inference_settings = _inference_settings()
    text_settings = dict(inference_settings.pop("text", {}))
    registry = compile_registry(payload.available_operations)
    request_input = _request_input_payload(payload)
    request = {
        "model": OPENAI_MODEL,
        "instructions": (
            "Return exactly one Jarvis action by calling exactly one supplied tool. "
            "Use only the supplied context and any supplied operation index. Choose a terminal "
            "action when the conversation context alone is enough to respond. "
            "Use an operation only when external data, saved data, current state, "
            "or a side effect is required. Greetings, acknowledgements, thanks, "
            "and general conversation do not require operations. Do not call "
            "get_provider_status or get_operation_catalog merely to produce a "
            "conversational reply. If no operation is needed, choose answer. "
            "After a prior observation, use that observation to return a terminal "
            "action and do not call another operation. "
            "Do not include reasoning, analysis, or hidden thought."
        ),
        "input": json.dumps(request_input, ensure_ascii=False),
        "store": False,
        "text": text_settings,
        "tools": _native_tool_definitions(
            payload.available_operations,
            registry,
            include_operations=not payload.prior_observations,
        ),
        "tool_choice": "required",
    }
    request.update(inference_settings)
    return request, registry


def _request_input_payload(payload: LLMInputPayload) -> dict[str, Any]:
    """Project the source contract into the smaller payload sent to the model."""
    request_input = payload.model_dump(mode="json")
    if payload.prior_observations:
        request_input.pop("available_operations", None)
    else:
        request_input["available_operations"] = _compact_operation_index(
            payload.available_operations
        )
    return request_input


def _compact_operation_index(catalog: dict[str, Any]) -> dict[str, Any]:
    """Keep only metadata needed for model selection; schemas remain in tools."""
    return {
        "contract_version": catalog.get("contract_version"),
        "providers": [
            {
                "provider_id": provider.get("provider_id"),
                "operations": [
                    {
                        key: operation.get(key)
                        for key in (
                            "provider_id",
                            "operation_id",
                            "description",
                            "availability",
                            "mode",
                            "risk_level",
                            "confirmation_required",
                            "what_it_can_do",
                            "what_it_cannot_do",
                            "limitations",
                        )
                        if key in operation
                    }
                    for operation in provider.get("operations", [])
                ],
            }
            for provider in catalog.get("providers", [])
        ],
    }


def _conversation_update_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transition": {"type": "string", "enum": [
                "continue_topic", "switch_topic", "answer_pending_question",
                "respond_to_confirmation", "start_request",
                "continue_unresolved_intent", "end_conversation",
            ]},
            "current_topic": {"type": ["string", "null"]},
            "previous_topic": {"type": ["string", "null"]},
            "pending_question": {"type": ["string", "null"]},
            "unresolved_intent": {"type": ["string", "null"]},
        },
        "required": ["transition", "current_topic", "previous_topic", "pending_question", "unresolved_intent"],
    }


def _native_tool_definitions(catalog: dict[str, Any], registry: NativeToolRegistry, *, include_operations: bool) -> list[dict[str, Any]]:
    operations = {
        (operation.get("provider_id"), operation.get("operation_id")): operation
        for provider in catalog.get("providers", [])
        for operation in provider.get("operations", [])
    }
    tools: list[dict[str, Any]] = []
    if include_operations:
        for entry in registry.entries.values():
            operation = operations[(entry.provider_id, entry.operation_id)]
            tools.append({
                "type": "function", "name": entry.name, "strict": True,
                "description": operation.get("description") or f"{entry.provider_id}.{entry.operation_id}",
                "parameters": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"arguments": entry.openai_schema, "conversation_update": _conversation_update_schema()},
                    "required": ["arguments", "conversation_update"],
                },
            })
    message_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"message": {"type": "string", "minLength": 1}, "conversation_update": _conversation_update_schema()},
        "required": ["message", "conversation_update"],
    }
    for action in ("answer", "ask_clarification", "request_confirmation", "refuse"):
        tools.append({
            "type": "function", "name": f"jarvis_control_{action}", "strict": True,
            "description": f"Return the Jarvis terminal action: {action}.",
            "parameters": deepcopy(message_schema),
        })
    return tools


def _normalize_native_tool_response(response: Any, registry: NativeToolRegistry) -> dict[str, Any]:
    calls = [item for item in (getattr(response, "output", None) or []) if getattr(item, "type", None) == "function_call"]
    if len(calls) != 1:
        raise OpenAIResponseValidationError(f"OpenAI must return exactly one function call; received {len(calls)}")
    call = calls[0]
    name = getattr(call, "name", None)
    raw_arguments = getattr(call, "arguments", None)
    try:
        values = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
    except json.JSONDecodeError:
        raise OpenAIResponseValidationError("OpenAI returned malformed tool arguments") from None
    if not isinstance(name, str) or not isinstance(values, dict):
        raise OpenAIResponseValidationError("OpenAI returned an invalid function call")
    prefix = "jarvis_control_"
    if name.startswith(prefix):
        action = name[len(prefix):]
        if action not in {"answer", "ask_clarification", "request_confirmation", "refuse"}:
            raise OpenAIResponseValidationError(f"Unknown control tool: {name}")
        if set(values) != {"message", "conversation_update"}:
            raise OpenAIResponseValidationError("Control tool arguments do not match its schema")
        return {
            "contract_version": "1", "action": action,
            "message": values.get("message"),
            "conversation_update": values.get("conversation_update"),
        }
    try:
        if set(values) != {"arguments", "conversation_update"}:
            raise NativeToolArgumentsError(
                "Operation tool arguments do not match its wrapper schema"
            )
        entry = registry.resolve(name)
        arguments = normalize_arguments(values.get("arguments"), entry)
    except (NativeToolSchemaError, NativeToolArgumentsError) as exc:
        raise OpenAIResponseValidationError(str(exc)) from None
    return {
        "contract_version": "1", "action": "call_operation",
        "provider_id": entry.provider_id, "operation_id": entry.operation_id,
        "arguments": arguments,
        "conversation_update": values.get("conversation_update"),
    }


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
