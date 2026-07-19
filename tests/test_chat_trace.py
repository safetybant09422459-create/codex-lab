import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.agent_host import AgentContractError, AgentHost, TurnInput
from backend.chat_trace import (
    ChatTraceRecorder, ChatTraceStore, CONSULTATION_MAX_BYTES, FULL_MAX_BYTES,
    aggregate_usage, bounded_json, build_bundle, detect_anomalies, extract_usage,
    sanitize,
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
