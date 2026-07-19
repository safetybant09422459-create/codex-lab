import json
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.agent_host import AgentContractError, AgentHost, TurnInput
from backend.chat_trace import (
    ChatTraceRecorder, ChatTraceStore, CONSULTATION_MAX_BYTES, FULL_MAX_BYTES,
    aggregate_usage, bounded_json, build_bundle, detect_anomalies, extract_usage,
    collect_environment, sanitize,
)
from tests.fake_llm_client import FakeLLMClient


def _answer(message="answer"):
    return {"contract_version": "1", "action": "answer", "message": message, "conversation_update": {"transition": "start_request"}}


class ChatTraceStoreTest(unittest.TestCase):
    def test_ring_order_get_list_and_clear(self) -> None:
        store = ChatTraceStore(50)
        for index in range(55):
            store.put({"turn_id": f"turn-{index}"})
        self.assertEqual(len(store.list()), 50)
        self.assertEqual(store.list()[0]["turn_id"], "turn-54")
        self.assertIsNone(store.get("turn-0"))
        self.assertEqual(store.get("turn-54")["turn_id"], "turn-54")
        self.assertEqual(store.clear(), 50)
        self.assertEqual(store.list(), [])

    def test_basic_thread_safety(self) -> None:
        store = ChatTraceStore()
        threads = [threading.Thread(target=lambda n=n: store.put({"turn_id": f"t-{n}"})) for n in range(100)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(len(store.list()), 50)

    def test_recorder_store_failure_does_not_escape(self) -> None:
        store = ChatTraceStore()
        store.put = lambda _trace: (_ for _ in ()).throw(RuntimeError("store failed"))
        recorder = ChatTraceRecorder(store, {})
        recorder.start_turn("turn", "session", {"text": "hello"})
        recorder.stage_start("turn", "context_assembly", {})
        recorder.complete("turn", "answer")


class RedactionTest(unittest.TestCase):
    def test_recursive_redaction_and_original_unchanged(self) -> None:
        original = {
            "api_key": "dummy-api-key", "nested": [{"password": "dummy-password"}],
            "header": "Authorization: Bearer dummy-token", "cookie": "dummy-cookie",
            "safe": "hello",
        }
        safe = sanitize(original)
        self.assertEqual(safe["api_key"], "[REDACTED]")
        self.assertEqual(safe["nested"][0]["password"], "[REDACTED]")
        self.assertEqual(safe["cookie"], "[REDACTED]")
        self.assertNotIn("dummy-token", json.dumps(safe))
        self.assertEqual(safe["safe"], "hello")
        self.assertEqual(original["api_key"], "dummy-api-key")

    def test_exception_and_unsupported_object_are_safe(self) -> None:
        self.assertNotIn("dummy-token", str(sanitize(RuntimeError("Bearer dummy-token"))))
        self.assertNotIn("object at", json.dumps(sanitize(object())))


class TruncationTest(unittest.TestCase):
    def test_large_string_dict_and_list_keep_metadata(self) -> None:
        safe = sanitize({"large": "x" * 40000, "items": list(range(100)), **{f"k{i}": i for i in range(120)}})
        self.assertTrue(safe["large"]["_truncated"])
        self.assertGreater(safe["large"]["_original_bytes"], 32000)
        self.assertTrue(safe["items"][-1]["_items_truncated"])
        self.assertTrue(safe["_items_truncated"])

    def test_bundle_limits(self) -> None:
        trace = {"turn_id": "t", "user_input": "x" * 300000, "stages": {}, "llm_calls": []}
        self.assertLessEqual(len(build_bundle(trace, "consultation").encode()), CONSULTATION_MAX_BYTES)
        self.assertLessEqual(len(build_bundle(trace, "full").encode()), FULL_MAX_BYTES)
        self.assertIn("_original_bytes", bounded_json("x" * 300000, 1000))

    def test_consultation_is_diagnostic_summary_and_keeps_tail(self) -> None:
        schema = {"input_schema": {"properties": {"huge": "x" * 50000}}, "output_schema": {"type": "object"}}
        payload = {"prior_observations": [], "available_operations": {"providers": [schema]}, "private_blob": "x" * 50000}
        usage_1 = {"input_tokens": 12000, "cached_input_tokens": 100, "output_tokens": 200, "reasoning_tokens": 50, "total_tokens": 12200}
        usage_2 = {"input_tokens": 12000, "cached_input_tokens": 200, "output_tokens": 422, "reasoning_tokens": 60, "total_tokens": 12422}
        trace = {
            "turn_id": "turn", "completed_at": "now", "overall_status": "warning",
            "environment": {"git_dirty": False}, "user_input": {"text": "旅行一覧を見せて"},
            "final_answer": "旅行一覧はまだ登録されていません。", "error_category": None,
            "error_message": "diagnostic error retained", "total_duration_ms": 10358,
            "token_usage": {"input_tokens_total": 24000, "cached_input_tokens_total": 300, "output_tokens_total": 622, "reasoning_tokens_total": 110, "total_tokens": 24622},
            "anomaly_flags": detect_anomalies({"completed_at": "now", "total_duration_ms": 10358, "token_usage": {"total_tokens": 24622}, "llm_calls": [{"step": 1, "duration_ms": 7675, "usage": usage_1}], "stages": {}}),
            "llm_calls": [
                {"step": 1, "request": {"model": "gpt", "tool_names": ["travel_get_trips"], "operation_tool_count": 1, "control_tool_count": 3, "llm_input_payload": payload, "tool_definitions": [schema]}, "response": {"status": "completed", "function_call_count": 1, "function_call_names": ["travel_get_trips"], "normalized_action": {"action": "call_operation", "provider_id": "travel", "operation_id": "get_trips", "arguments": {}}}, "usage": usage_1, "duration_ms": 7675},
                {"step": 2, "request": {"model": "gpt", "tool_names": ["jarvis_control_answer"], "operation_tool_count": 0, "control_tool_count": 1, "llm_input_payload": {**payload, "prior_observations": [{}]}, "tool_definitions": [schema]}, "response": {"status": "completed", "function_call_count": 1, "function_call_names": ["jarvis_control_answer"], "normalized_action": {"action": "answer"}}, "usage": usage_2, "duration_ms": 2000},
            ],
            "stages": {
                "context_assembly": {"status": "success", "output": {"turn_context": {"active_entities": [], "pending_question": None}, "conversation_context_count": 1, "memory_context_count": 0, "activation_candidates_count": 0, "capability_context_count": 2, "session_info": {"session_id": "safe"}}, "duration_ms": 1},
                "operation_catalog": {"status": "success", "output": {"provider_count": 2, "operation_count": 3, "implemented_operation_count": 2, "available_operation_names": ["travel.get_trips", "jarvis.get_capabilities"], "catalog": schema}, "duration_ms": 1},
                "action_validation_1": {"status": "success", "output": {"action": "call_operation", "provider_id": "travel", "operation_id": "get_trips"}},
                "runtime_execution": {"status": "success", "input": {"provider_id": "travel", "operation_id": "get_trips", "runtime_arguments": {}, "role": "admin", "confirmed": False}, "output": {"success": True, "execution_mode": "local_travel_read", "result": {"trips": [], "source": "local_travel_read"}}, "duration_ms": 10},
                "observation_build": {"status": "success", "output": {"status": "success", "provider_id": "travel", "operation_id": "get_trips", "counts": {"trip_count": 0}, "facts": {"trip_count": 0, "titles": []}, "limitations": [], "provenance": {"source": "local_travel_read"}, "entities": [], "raw_result": {"large": "x" * 50000}}, "duration_ms": 1},
                "action_validation_2": {"status": "success", "output": {"action": "answer"}},
            },
        }
        consultation = build_bundle(trace, "consultation")
        self.assertLessEqual(len(consultation.encode()), CONSULTATION_MAX_BYTES)
        for omitted in ('"input_schema"', '"output_schema"', '"tool_definitions"', '"llm_input_payload"', '"catalog"'):
            self.assertNotIn(omitted, consultation)
        for retained in ("travel.get_trips", '"selected_provider": "travel"', '"success": true', "local_travel_read", '"trip_count": 0', "Final Answer", "旅行一覧はまだ登録", "Token Usage", "llm_call_1", "llm_call_2", "diagnostic error retained"):
            self.assertIn(retained, consultation)
        full = build_bundle(trace, "full")
        self.assertLessEqual(len(full.encode()), FULL_MAX_BYTES)
        self.assertIn("llm_input_payload", full)
        self.assertIn("tool_definitions", full)


class GitEnvironmentTest(unittest.TestCase):
    def _run(self, stdout="", returncode=0):
        result = Mock(stdout=stdout, returncode=returncode)
        if returncode:
            return Mock(side_effect=RuntimeError("git failed"))
        return Mock(return_value=result)

    def test_clean_and_dirty_are_booleans_and_use_project_root(self) -> None:
        for status, expected in (("", False), (" M file.py\n", True)):
            calls = [Mock(stdout="sha\n"), Mock(stdout="branch\n"), Mock(stdout=status)]
            with patch("backend.chat_trace.subprocess.run", side_effect=calls) as run:
                env = collect_environment(Path("/tmp/project"), "Jarvis", {})
            self.assertIs(env["git_dirty"], expected)
            self.assertEqual(env["project_root"], "/tmp/project")
            self.assertEqual(run.call_args_list[2].args[0][:3], ["git", "-C", "/tmp/project"])

    def test_git_failure_is_unknown_and_does_not_escape(self) -> None:
        with patch("backend.chat_trace.subprocess.run", side_effect=RuntimeError("secret stderr")):
            env = collect_environment(Path("/tmp/project"), "Jarvis", {})
        self.assertEqual(env["git_dirty"], "unknown")
        self.assertNotIn("secret stderr", json.dumps(env))


class UsageAndAnomalyTest(unittest.TestCase):
    def test_responses_usage_and_two_call_total(self) -> None:
        response = SimpleNamespace(usage=SimpleNamespace(
            input_tokens=10, input_tokens_details=SimpleNamespace(cached_tokens=3),
            output_tokens=5, output_tokens_details=SimpleNamespace(reasoning_tokens=2),
            total_tokens=15,
        ))
        usage = extract_usage(response)
        self.assertEqual(usage, {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 5, "reasoning_tokens": 2, "total_tokens": 15})
        totals = aggregate_usage([{"usage": usage}, {"usage": usage}])
        self.assertEqual(totals["total_tokens"], 30)
        self.assertEqual(totals["reasoning_tokens_total"], 4)

    def test_missing_usage_is_null(self) -> None:
        self.assertTrue(all(value is None for value in extract_usage(object()).values()))
        self.assertTrue(all(value is None for value in aggregate_usage([{"usage": {}}]).values()))

    def test_deterministic_pipeline_anomalies(self) -> None:
        trace = {
            "error_category": "action_validation_error", "completed_at": "now",
            "llm_calls": [{"step": 2, "usage": {"total_tokens": None}}],
            "stages": {
                "action_validation_1": {"status": "success", "output": {"action": "call_operation", "provider_id": "travel", "operation_id": "get_trips"}},
                "action_validation_2": {"status": "error", "input": {"action": "call_operation", "provider_id": "travel", "operation_id": "get_trips"}, "error_message": "operation budget was exhausted"},
                "runtime_execution": {"status": "success", "output": {"success": True}},
                "observation_build": {"status": "success"},
            },
        }
        codes = {flag["code"] for flag in detect_anomalies(trace)}
        self.assertIn("OPERATION_AFTER_OBSERVATION", codes)
        self.assertIn("SAME_OPERATION_SELECTED_TWICE", codes)
        self.assertIn("LLM_USAGE_MISSING", codes)

    def test_performance_thresholds_are_warnings(self) -> None:
        trace = {"completed_at": "now", "total_duration_ms": 10000, "token_usage": {"total_tokens": 20000}, "llm_calls": [{"step": 1, "duration_ms": 5000, "usage": {"total_tokens": 20000}}], "stages": {}}
        flags = detect_anomalies(trace)
        self.assertEqual({"HIGH_TOKEN_USAGE", "SLOW_LLM_CALL", "SLOW_TURN"}, {flag["code"] for flag in flags})
        self.assertTrue(all(flag["severity"] == "warning" for flag in flags))

    def test_performance_below_threshold_and_missing_usage_have_no_token_warning(self) -> None:
        trace = {"completed_at": "now", "total_duration_ms": 9999, "token_usage": {}, "llm_calls": [{"step": 1, "duration_ms": 4999, "usage": {"total_tokens": None}}], "stages": {}}
        codes = {flag["code"] for flag in detect_anomalies(trace)}
        self.assertNotIn("HIGH_TOKEN_USAGE", codes)
        self.assertNotIn("SLOW_LLM_CALL", codes)
        self.assertNotIn("SLOW_TURN", codes)


class PipelineRecorderTest(unittest.TestCase):
    def runtime(self):
        runtime = Mock()
        runtime.get_capability_catalog.return_value = {"providers": []}
        runtime.get_operation_catalog.return_value = {"contract_version": "1", "providers": []}
        return runtime

    def test_direct_answer_records_success_and_skipped_stages(self) -> None:
        store = ChatTraceStore()
        recorder = ChatTraceRecorder(store, {"configured_model": "fake"})
        result = AgentHost(FakeLLMClient(_answer()), self.runtime(), trace_recorder=recorder).run_turn(
            TurnInput(session_id="s", channel="chat", normalized_input={"text": "hello"})
        )
        trace = store.get(result.trace.turn_id)
        self.assertEqual(trace["overall_status"], "success")
        self.assertEqual(trace["stages"]["runtime_execution"]["status"], "skipped")
        self.assertEqual(trace["stages"]["final_answer"]["status"], "success")

    def test_invalid_first_action_is_saved_as_failure(self) -> None:
        store = ChatTraceStore()
        recorder = ChatTraceRecorder(store, {})
        invalid = _answer()
        invalid["unexpected"] = True
        with self.assertRaises(AgentContractError):
            AgentHost(FakeLLMClient(invalid), self.runtime(), trace_recorder=recorder).run_turn(
                TurnInput(session_id="s", channel="chat", normalized_input={"text": "hello"})
            )
        trace = store.list()[0]
        self.assertEqual(trace["overall_status"], "error")
        self.assertEqual(trace["stages"]["action_validation_1"]["status"], "error")
        self.assertIn("ACTION_VALIDATION_FAILED", {flag["code"] for flag in trace["anomaly_flags"]})


if __name__ == "__main__":
    unittest.main()
