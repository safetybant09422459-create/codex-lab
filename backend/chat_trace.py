from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import re
import subprocess
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

from pydantic import BaseModel


TRACE_VERSION = "1"
DEFAULT_TRACE_LIMIT = 50
CONSULTATION_MAX_BYTES = 40 * 1024
FULL_MAX_BYTES = 200 * 1024
FIELD_MAX_BYTES = 32 * 1024
LIST_ITEM_LIMIT = 20
REDACTED = "[REDACTED]"

STAGE_NAMES = (
    "turn_started", "context_assembly", "operation_catalog", "llm_call_1",
    "action_validation_1", "runtime_execution", "observation_build",
    "llm_call_2", "action_validation_2", "final_answer", "turn_completed",
)

_SECRET_KEY_NAMES = {
    "api_key", "apikey", "authorization", "token", "access_token",
    "refresh_token", "cookie", "password", "passwd", "secret",
    "client_secret", "developer_token", "immich_api_key",
}
_SECRET_VALUES = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"(?i)\b(?:Authorization|Cookie)\s*:\s*[^\r\n]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_text(value: str) -> str:
    result = value
    for pattern in _SECRET_VALUES:
        if pattern.pattern.startswith("(?i)(https?"):
            result = pattern.sub(r"\1[REDACTED]@", result)
        else:
            result = pattern.sub(REDACTED, result)
    return result


def sanitize(value: Any, *, _depth: int = 0) -> Any:
    """Return a detached, JSON-safe, recursively redacted value."""
    try:
        if _depth > 12:
            return {"_truncated": True, "_preview": "maximum depth reached"}
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return _truncate_field(sanitize_text(value))
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "[BINARY OMITTED]"
        if isinstance(value, BaseException):
            return sanitize_text(str(value) or value.__class__.__name__)
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            items = list(value.items())
            for key, item in items[:LIST_ITEM_LIMIT * 5]:
                safe_key = sanitize_text(str(key))
                result[safe_key] = REDACTED if _is_secret_key(safe_key) else sanitize(item, _depth=_depth + 1)
            if len(items) > LIST_ITEM_LIMIT * 5:
                result["_items_truncated"] = True
                result["_original_count"] = len(items)
                result["_included_count"] = LIST_ITEM_LIMIT * 5
            return result
        if isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)
            result = [sanitize(item, _depth=_depth + 1) for item in items[:LIST_ITEM_LIMIT]]
            if len(items) > LIST_ITEM_LIMIT:
                result.append({
                    "_items_truncated": True,
                    "_original_count": len(items),
                    "_included_count": LIST_ITEM_LIMIT,
                })
            return result
        return {"_type": value.__class__.__name__, "_value": "[UNSUPPORTED OBJECT OMITTED]"}
    except Exception:
        return "[SANITIZATION FAILED]"


def _truncate_field(value: str, limit: int = FIELD_MAX_BYTES) -> str | dict[str, Any]:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value
    preview = encoded[: max(0, limit - 256)].decode("utf-8", errors="ignore")
    return {"_truncated": True, "_original_bytes": len(encoded), "_preview": preview}


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return normalized in _SECRET_KEY_NAMES


def bounded_json(value: Any, max_bytes: int) -> str:
    safe = sanitize(value)
    text = json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    wrapper = {
        "_truncated": True,
        "_original_bytes": len(encoded),
        "_preview": encoded[: max(0, max_bytes - 160)].decode("utf-8", errors="ignore"),
    }
    text = json.dumps(wrapper, ensure_ascii=False, indent=2)
    while len(text.encode("utf-8")) > max_bytes and wrapper["_preview"]:
        wrapper["_preview"] = wrapper["_preview"][:-256]
        text = json.dumps(wrapper, ensure_ascii=False, indent=2)
    return text


def empty_stage(name: str) -> dict[str, Any]:
    return {
        "name": name, "status": "pending", "started_at": None,
        "completed_at": None, "duration_ms": None, "input": None,
        "output": None, "error_category": None, "error_message": None,
    }


def collect_environment(root: Path, app_title: str, settings: dict[str, Any]) -> dict[str, Any]:
    def git_value(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=root, check=True, capture_output=True,
                text=True, timeout=2,
            ).stdout.strip() or None
        except Exception:
            return None

    try:
        sdk_version = importlib.metadata.version("openai")
    except importlib.metadata.PackageNotFoundError:
        sdk_version = None
    status = git_value("status", "--porcelain")
    return sanitize({
        "git_commit_sha": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "git_dirty": None if status is None else bool(status),
        "service_started_at": utc_now(),
        "python_version": platform.python_version(),
        "jarvis_app_title": app_title,
        "configured_model": settings.get("model"),
        "reasoning_effort": settings.get("reasoning_effort") or None,
        "verbosity": settings.get("verbosity") or None,
        "max_output_tokens": settings.get("max_output_tokens"),
        "timeout_seconds": settings.get("timeout_seconds"),
        "openai_sdk_version": sdk_version,
        "process_id": os.getpid(),
    })


class ChatTraceStore:
    def __init__(self, max_turns: int = DEFAULT_TRACE_LIMIT) -> None:
        if max_turns < 1 or max_turns > DEFAULT_TRACE_LIMIT:
            raise ValueError("max_turns must be between 1 and 50")
        self.max_turns = max_turns
        self._items: deque[dict[str, Any]] = deque(maxlen=max_turns)
        self._lock = RLock()

    def put(self, trace: dict[str, Any]) -> None:
        item = sanitize(trace)
        with self._lock:
            self._items = deque(
                (current for current in self._items if current.get("turn_id") != item.get("turn_id")),
                maxlen=self.max_turns,
            )
            self._items.append(item)

    def get(self, turn_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in reversed(self._items):
                if item.get("turn_id") == turn_id:
                    return deepcopy(item)
        return None

    def list(self, limit: int = DEFAULT_TRACE_LIMIT) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(reversed(self._items))[:limit])

    def clear(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            return count


class ChatTraceRecorder:
    """Best-effort observer. Every public method is fail-open for Chat."""

    def __init__(self, store: ChatTraceStore, environment: dict[str, Any]) -> None:
        self.store = store
        self.environment = sanitize(environment)
        self._active: dict[str, dict[str, Any]] = {}
        self._timers: dict[tuple[str, str], float] = {}
        self._lock = RLock()

    def start_turn(self, turn_id: str, session_id: str, user_input: Any) -> None:
        try:
            with self._lock:
                trace = {
                    "trace_version": TRACE_VERSION, "turn_id": turn_id,
                    "session_id": session_id, "created_at": utc_now(),
                    "completed_at": None, "overall_status": "running",
                    "user_input": sanitize(user_input), "final_answer": None,
                    "error_category": None, "error_message": None,
                    "environment": deepcopy(self.environment),
                    "stages": {name: empty_stage(name) for name in STAGE_NAMES},
                    "llm_calls": [], "token_usage": _empty_usage(),
                    "anomaly_flags": [], "total_duration_ms": None,
                }
                self._active[turn_id] = trace
                self._stage_start_locked(trace, "turn_started", {"user_input": user_input})
                self._stage_finish_locked(trace, "turn_started", "success", {"session_id": session_id})
                self.store.put(trace)
        except Exception:
            return

    def stage_start(self, turn_id: str, name: str, input_value: Any = None) -> None:
        try:
            with self._lock:
                trace = self._active.get(turn_id)
                if trace:
                    self._stage_start_locked(trace, name, input_value)
        except Exception:
            return

    def stage_finish(self, turn_id: str, name: str, output: Any = None, *, status: str = "success") -> None:
        try:
            with self._lock:
                trace = self._active.get(turn_id)
                if trace:
                    self._stage_finish_locked(trace, name, status, output)
        except Exception:
            return

    def stage_error(self, turn_id: str, name: str, category: str, error: Any) -> None:
        try:
            with self._lock:
                trace = self._active.get(turn_id)
                if trace:
                    self._stage_finish_locked(trace, name, "error", None, category, error)
                    trace["error_category"] = category
                    trace["error_message"] = sanitize(error)
                    self.store.put(trace)
        except Exception:
            return

    def record_llm_call(self, turn_id: str, call: dict[str, Any]) -> None:
        try:
            with self._lock:
                trace = self._active.get(turn_id)
                if not trace:
                    return
                safe_call = sanitize(call)
                trace["llm_calls"].append(safe_call)
                trace["token_usage"] = aggregate_usage(trace["llm_calls"])
                self.store.put(trace)
        except Exception:
            return

    def complete(self, turn_id: str, final_answer: str | None = None, *, error_category: str | None = None, error: Any = None) -> None:
        try:
            with self._lock:
                trace = self._active.get(turn_id)
                if not trace:
                    return
                trace["final_answer"] = sanitize(final_answer)
                if error_category:
                    if not trace.get("error_category"):
                        trace["error_category"] = error_category
                    if not trace.get("error_message"):
                        trace["error_message"] = sanitize(error)
                for stage in trace["stages"].values():
                    if stage["status"] in {"pending", "running"}:
                        stage["status"] = "skipped"
                        if stage["started_at"] and not stage["completed_at"]:
                            stage["completed_at"] = utc_now()
                completed = trace["stages"]["turn_completed"]
                completed.update({"status": "success" if not error_category else "error", "started_at": utc_now(), "completed_at": utc_now(), "duration_ms": 0.0})
                trace["completed_at"] = utc_now()
                trace["total_duration_ms"] = _iso_duration_ms(trace["created_at"], trace["completed_at"])
                trace["anomaly_flags"] = detect_anomalies(trace)
                severities = {flag["severity"] for flag in trace["anomaly_flags"]}
                trace["overall_status"] = "error" if (trace.get("error_category") not in {None, "confirmation_required"} or "error" in severities) else "warning" if (trace.get("error_category") == "confirmation_required" or "warning" in severities) else "success"
                self.store.put(trace)
                self._active.pop(turn_id, None)
                for key in [key for key in self._timers if key[0] == turn_id]:
                    self._timers.pop(key, None)
        except Exception:
            return

    def _stage_start_locked(self, trace: dict[str, Any], name: str, input_value: Any) -> None:
        if name not in trace["stages"]:
            return
        stage = trace["stages"][name]
        stage.update({"status": "running", "started_at": utc_now(), "input": sanitize(input_value)})
        self._timers[(trace["turn_id"], name)] = perf_counter()

    def _stage_finish_locked(self, trace: dict[str, Any], name: str, status: str, output: Any, category: str | None = None, error: Any = None) -> None:
        if name not in trace["stages"]:
            return
        stage = trace["stages"][name]
        started = self._timers.pop((trace["turn_id"], name), None)
        stage.update({
            "status": status, "completed_at": utc_now(),
            "duration_ms": round((perf_counter() - started) * 1000, 3) if started else 0.0,
            "output": sanitize(output), "error_category": category,
            "error_message": sanitize(error) if error is not None else None,
        })
        if name == "runtime_execution" and isinstance(output, dict) and output.get("success") is False:
            if output.get("permission_denied") is True:
                trace["error_category"] = "permission_denied"
            elif output.get("confirmation_required") is True and output.get("blocked") is True:
                trace["error_category"] = "confirmation_required"
            else:
                trace["error_category"] = "runtime_error"
            trace["error_message"] = sanitize(output.get("reason") or output.get("errors") or "Runtime returned success=false")
        self.store.put(trace)


def _empty_usage() -> dict[str, int]:
    return {
        "input_tokens_total": 0, "cached_input_tokens_total": 0,
        "output_tokens_total": 0, "reasoning_tokens_total": 0,
        "total_tokens": 0,
    }


def extract_usage(response: Any) -> dict[str, int | None]:
    usage = _value(response, "usage")
    input_details = _value(usage, "input_tokens_details")
    output_details = _value(usage, "output_tokens_details")
    return {
        "input_tokens": _int_or_none(_value(usage, "input_tokens")),
        "cached_input_tokens": _int_or_none(_value(input_details, "cached_tokens")),
        "output_tokens": _int_or_none(_value(usage, "output_tokens")),
        "reasoning_tokens": _int_or_none(_value(output_details, "reasoning_tokens")),
        "total_tokens": _int_or_none(_value(usage, "total_tokens")),
    }


def aggregate_usage(calls: list[dict[str, Any]]) -> dict[str, int]:
    result = _empty_usage()
    mapping = {
        "input_tokens": "input_tokens_total", "cached_input_tokens": "cached_input_tokens_total",
        "output_tokens": "output_tokens_total", "reasoning_tokens": "reasoning_tokens_total",
        "total_tokens": "total_tokens",
    }
    for call in calls:
        usage = call.get("usage") or {}
        for source, target in mapping.items():
            value = usage.get(source)
            if isinstance(value, int):
                result[target] += value
    return result


def detect_anomalies(trace: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    stages = trace.get("stages", {})
    category = trace.get("error_category")

    def add(severity: str, code: str, stage: str, message: str, evidence: Any) -> None:
        flags.append({"severity": severity, "code": code, "stage": stage, "message": message, "evidence": sanitize(evidence)})

    category_rules = {
        "timeout": ("error", "LLM_TIMEOUT", "llm_call", "LLM request timed out"),
        "provider_request_error": ("error", "LLM_REQUEST_FAILED", "llm_call", "LLM provider request failed"),
        "configuration_error": ("error", "LLM_REQUEST_FAILED", "llm_call_1", "LLM provider configuration failed"),
        "provider_refusal": ("error", "LLM_REFUSED", "llm_call", "LLM refused the request"),
        "provider_incomplete": ("error", "LLM_RESPONSE_INCOMPLETE", "llm_call", "LLM response was incomplete"),
        "runtime_error": ("error", "RUNTIME_FAILED", "runtime_execution", "Runtime execution failed"),
        "permission_denied": ("warning", "PERMISSION_DENIED", "runtime_execution", "Runtime denied permission"),
        "confirmation_required": ("warning", "CONFIRMATION_REQUIRED", "runtime_execution", "Runtime requires confirmation"),
        "observation_error": ("error", "OBSERVATION_BUILD_FAILED", "observation_build", "Observation build failed"),
        "final_answer_missing": ("error", "FINAL_ANSWER_MISSING", "final_answer", "Final answer is missing"),
    }
    if category in category_rules:
        severity, code, stage, message = category_rules[category]
        add(severity, code, stage, message, {"error_category": category, "error_message": trace.get("error_message")})
    for call in trace.get("llm_calls", []):
        step = call.get("step")
        if not call.get("usage") or all(value is None for value in call.get("usage", {}).values()):
            add("info", "LLM_USAGE_MISSING", f"llm_call_{step}", "Token usage was not returned", {"step": step})
        if call.get("error_category") and step == 2:
            add("error", "FINAL_LLM_FAILED", "llm_call_2", "Final LLM call failed", {"error_category": call.get("error_category")})
    av1, av2 = stages.get("action_validation_1", {}), stages.get("action_validation_2", {})
    if av1.get("status") == "error":
        add("error", "ACTION_VALIDATION_FAILED", "action_validation_1", "First Action contract validation failed", av1.get("error_message"))
    if av2.get("status") == "error":
        code = "OPERATION_AFTER_OBSERVATION" if "operation budget" in str(av2.get("error_message")) else "FINAL_ACTION_INVALID"
        add("error", code, "action_validation_2", "Final Action contract validation failed", av2.get("error_message"))
    first = av1.get("output") or {}
    second = av2.get("input") or {}
    if first.get("action") == "call_operation" and second.get("action") == "call_operation" and (first.get("provider_id"), first.get("operation_id")) == (second.get("provider_id"), second.get("operation_id")):
        add("error", "SAME_OPERATION_SELECTED_TWICE", "action_validation_2", "The same operation was selected twice", {"provider_id": first.get("provider_id"), "operation_id": first.get("operation_id")})
    runtime, observation = stages.get("runtime_execution", {}), stages.get("observation_build", {})
    runtime_output = runtime.get("output") or {}
    if runtime.get("status") in {"success", "warning"} and runtime_output.get("success") is False and not runtime_output.get("permission_denied") and not (runtime_output.get("confirmation_required") and runtime_output.get("blocked")):
        add("error", "RUNTIME_FAILED", "runtime_execution", "Runtime returned success=false", runtime_output)
    if runtime_output.get("permission_denied") is True:
        add("error", "PERMISSION_DENIED", "runtime_execution", "Runtime denied permission", {"role": runtime_output.get("role"), "reason": runtime_output.get("reason")})
    if runtime_output.get("confirmation_required") is True and runtime_output.get("blocked") is True:
        add("warning", "CONFIRMATION_REQUIRED", "runtime_execution", "Runtime requires confirmation", {"confirmed": runtime_output.get("confirmed"), "reason": runtime_output.get("reason")})
    if runtime.get("status") == "success" and observation.get("status") in {"pending", "skipped", "error"}:
        add("error", "RUNTIME_SUCCEEDED_OBSERVATION_MISSING", "observation_build", "Runtime completed but no Observation was produced", {"runtime_status": runtime.get("status"), "observation_status": observation.get("status")})
    if not trace.get("completed_at"):
        add("error", "TURN_NOT_COMPLETED", "turn_completed", "Turn did not reach completion", {"overall_status": trace.get("overall_status")})
    return flags


def primary_anomaly(trace: dict[str, Any]) -> dict[str, Any] | None:
    flags = trace.get("anomaly_flags") or detect_anomalies(trace)
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(flags, key=lambda flag: order.get(flag.get("severity"), 3))[0] if flags else None


def trace_summary(trace: dict[str, Any]) -> dict[str, Any]:
    environment = trace.get("environment", {})
    usage = trace.get("token_usage", {})
    return sanitize({
        "turn_id": trace.get("turn_id"), "created_at": trace.get("created_at"),
        "completed_at": trace.get("completed_at"), "overall_status": trace.get("overall_status"),
        "user_input_preview": _preview(trace.get("user_input")),
        "final_answer_preview": _preview(trace.get("final_answer")),
        "primary_anomaly": primary_anomaly(trace),
        "model": environment.get("configured_model"),
        "total_tokens": usage.get("total_tokens"),
        "total_duration_ms": trace.get("total_duration_ms"),
    })


def build_bundle(trace: dict[str, Any], mode: str) -> str:
    safe = sanitize(trace)
    if mode == "full":
        return bounded_json({"title": "Jarvis Chat Trace Bundle v1", "mode": "full", "trace": safe}, FULL_MAX_BYTES)
    anomaly = primary_anomaly(safe)
    stages = safe.get("stages", {})
    calls = safe.get("llm_calls", [])
    sections = [
        "Jarvis Chat Trace Bundle v1",
        "\n1. Environment\n" + bounded_json(safe.get("environment"), 5000),
        "\n2. Turn Summary\n" + bounded_json(trace_summary(safe), 4000),
        "\n3. Primary Suspect\n" + bounded_json(anomaly or {"stage": "none", "message": "No anomaly detected"}, 3000),
        "\n4. Anomaly Flags\n" + bounded_json(safe.get("anomaly_flags"), 5000),
        "\n5. Pipeline Summary\n" + bounded_json([{"name": item.get("name"), "status": item.get("status"), "duration_ms": item.get("duration_ms"), "error_category": item.get("error_category")} for item in stages.values()], 5000),
        "\n6. User Input\n" + bounded_json(safe.get("user_input"), 3000),
        "\n7. Context Summary\n" + bounded_json(stages.get("context_assembly"), 4000),
        "\n8. Operation Catalog Summary\n" + bounded_json(stages.get("operation_catalog"), 3000),
        "\n9. LLM Call #1\n" + bounded_json(calls[0] if calls else None, 5000),
        "\n10. Action #1\n" + bounded_json(stages.get("action_validation_1"), 3000),
        "\n11. Runtime\n" + bounded_json(stages.get("runtime_execution"), 4000),
        "\n12. Observation\n" + bounded_json(_consultation_observation(stages.get("observation_build")), 4000),
        "\n13. LLM Call #2\n" + bounded_json(calls[1] if len(calls) > 1 else None, 5000),
        "\n14. Final Action\n" + bounded_json(stages.get("action_validation_2"), 3000),
        "\n15. Final Answer\n" + bounded_json(safe.get("final_answer"), 3000),
        "\n16. Token Usage\n" + bounded_json(safe.get("token_usage"), 3000),
        "\n17. Timings\n" + bounded_json({"total_duration_ms": safe.get("total_duration_ms"), "stages": {name: stage.get("duration_ms") for name, stage in stages.items()}}, 3000),
        "\n18. Errors\n" + bounded_json({"error_category": safe.get("error_category"), "error_message": safe.get("error_message")}, 3000),
        "\n19. Truncation Notes\nLarge fields and arrays are bounded; markers preserve original byte/count metadata.",
    ]
    text = "\n".join(sections)
    if len(text.encode("utf-8")) <= CONSULTATION_MAX_BYTES:
        return text
    return bounded_json({"title": "Jarvis Chat Trace Bundle v1", "mode": "consultation", "content": text}, CONSULTATION_MAX_BYTES)


def _consultation_observation(stage: Any) -> Any:
    if not isinstance(stage, dict):
        return stage
    result = deepcopy(stage)
    output = result.get("output")
    if isinstance(output, dict) and "raw_result" in output:
        raw = output["raw_result"]
        output["raw_result"] = {"summary": _shape_summary(raw), "preview": sanitize(raw)}
    return result


def _shape_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "object", "keys": list(value)[:20], "count": len(value)}
    if isinstance(value, list):
        return {"type": "array", "count": len(value)}
    return {"type": type(value).__name__}


def _preview(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and "text" in value:
        value = value["text"]
    text = sanitize_text(str(value)).replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def _value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _iso_duration_ms(started: str, completed: str) -> float | None:
    try:
        return round((datetime.fromisoformat(completed) - datetime.fromisoformat(started)).total_seconds() * 1000, 3)
    except (TypeError, ValueError):
        return None
