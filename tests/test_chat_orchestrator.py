import json
import unittest
from unittest.mock import patch

from backend import chat_orchestrator, openai_adapter
from backend.chat_tool_policy import (
    CHAT_READ_EXECUTABLE_TOOLS,
    CHAT_TRAVEL_TOOL_ALLOWLIST,
    CHAT_WRITE_PENDING_TOOLS,
    get_chat_tool_execution_policy,
)


def json_generator(payload: dict[str, object]):
    def generate(**_kwargs: str) -> str:
        return json.dumps(payload, ensure_ascii=False)

    return generate


class FakeRuntimeService:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def execute_stub(self, tool_id, params, confirmed=False, role=None):
        self.calls.append(
            {
                "tool_id": tool_id,
                "params": params,
                "confirmed": confirmed,
                "role": role,
            }
        )
        if self.error is not None:
            raise self.error
        if isinstance(self.response, list):
            return self.response[len(self.calls) - 1]
        return self.response


class ChatOrchestratorTest(unittest.TestCase):
    def test_trip_list_proposes_get_trips(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=False,
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        self.assertEqual(
            result,
            {
                "action": "tool_proposal",
                "tool_id": "get_trips",
                "arguments": {},
                "confidence": "high",
                "reply": "旅行一覧を取得します。",
            },
        )
        self.assertNotIn("debug", result)

    def test_debug_includes_numeric_timings(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=True,
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "旅行一覧を取得します。",
                }
            ),
        )

        timings = result["debug"]["timings_ms"]
        self.assertEqual(
            set(timings),
            {
                "build_prompt",
                "llm_call",
                "json_parse",
                "policy_validation",
                "fallback",
                "total",
            },
        )
        self.assertTrue(
            all(isinstance(value, (int, float)) for value in timings.values())
        )

    def test_api_error_debug_still_includes_total(self) -> None:
        def raise_api_error(**_kwargs: str) -> str:
            raise openai_adapter.OpenAIRequestError("safe failure")

        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            debug=True,
            text_generator=raise_api_error,
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertIsInstance(result["debug"]["timings_ms"]["total"], float)
        self.assertGreaterEqual(result["debug"]["timings_ms"]["fallback"], 0)

    def test_default_adapter_error_debug_keeps_safe_timings(self) -> None:
        adapter_timings = {
            "api_call": 12.3,
            "response_text_extraction": 0.0,
            "total": 12.4,
        }

        with patch.object(
            chat_orchestrator,
            "generate_text_with_timings",
            side_effect=openai_adapter.OpenAIRequestError(
                "safe failure", timings_ms=adapter_timings
            ),
        ):
            result = chat_orchestrator.propose_travel_tool(
                "旅行一覧を見せて",
                debug=True,
            )

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(
            result["debug"]["openai_adapter"]["timings_ms"],
            adapter_timings,
        )

    def test_debug_includes_openai_adapter_timings_for_default_generator(self) -> None:
        payload = json.dumps(
            {
                "action": "needs_context",
                "reply": "対象を指定してください。",
            },
            ensure_ascii=False,
        )
        adapter_timings = {
            "api_call": 12.3,
            "response_text_extraction": 0.2,
            "total": 12.6,
        }

        with patch.object(
            chat_orchestrator,
            "generate_text_with_timings",
            return_value=(payload, adapter_timings),
        ):
            result = chat_orchestrator.propose_travel_tool(
                "旅行一覧を見せて",
                debug=True,
            )

        self.assertEqual(
            result["debug"]["openai_adapter"]["timings_ms"],
            adapter_timings,
        )

    def test_debug_does_not_expose_secrets_or_model_content(self) -> None:
        secret = "sk-debug-secret-value"

        def raise_secret_error(**_kwargs: str) -> str:
            raise RuntimeError(f"Bearer {secret} response body secret-response")

        result = chat_orchestrator.propose_travel_tool(
            f"Bearer {secret}",
            debug=True,
            text_generator=raise_secret_error,
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("secret-response", serialized)

    def test_named_trip_proposes_get_trips_without_inventing_id(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "福岡旅行を開いて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_trips",
                    "arguments": {},
                    "confidence": "medium",
                    "reply": "福岡旅行を探します。",
                }
            ),
        )

        self.assertEqual(result["tool_id"], "get_trips")
        self.assertEqual(result["arguments"], {})
        self.assertEqual(result["confidence"], "medium")

    def test_photo_request_without_experience_context_is_supported(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "アンパンマンミュージアムの写真見せて",
            text_generator=json_generator(
                {
                    "action": "needs_context",
                    "reply": "どの旅行の体験か確認するため、旅行または体験を先に選んでください。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")

    def test_tool_outside_allowlist_is_rejected(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "場所を一覧にして",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "get_spots",
                    "arguments": {},
                    "confidence": "high",
                    "reply": "場所を取得します。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertNotIn("tool_id", result)
        self.assertNotIn("get_spots", CHAT_TRAVEL_TOOL_ALLOWLIST)

    def test_update_experience_rejects_arguments_outside_chat_policy(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "体験のメモとタイトルを変えて",
            text_generator=json_generator(
                {
                    "action": "tool_proposal",
                    "tool_id": "update_experience",
                    "arguments": {
                        "experience_id": "experience-1",
                        "memo": "楽しかった",
                        "display_title": "変更後",
                    },
                    "confidence": "high",
                    "reply": "体験を更新します。",
                }
            ),
        )

        self.assertEqual(result["action"], "needs_context")
        self.assertNotIn("arguments", result)

    def test_non_json_model_response_falls_back_safely(self) -> None:
        result = chat_orchestrator.propose_travel_tool(
            "旅行一覧を見せて",
            text_generator=lambda **_kwargs: "旅行一覧を取得します。",
        )

        self.assertEqual(result["action"], "needs_context")

    def test_api_key_is_redacted_from_input_and_output(self) -> None:
        api_key = "sk-test-secret-value"
        captured: dict[str, str] = {}

        def generate(**kwargs: str) -> str:
            captured.update(kwargs)
            return json.dumps(
                {
                    "action": "needs_context",
                    "reply": f"確認が必要です: {api_key}",
                }
            )

        with patch.object(openai_adapter, "OPENAI_API_KEY", api_key):
            result = chat_orchestrator.propose_travel_tool(
                f"この値を使って: Bearer token-value {api_key}",
                text_generator=generate,
            )

        serialized_result = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(api_key, captured["input_text"])
        self.assertNotIn("token-value", captured["input_text"])
        self.assertNotIn(api_key, serialized_result)

    def test_proposal_only_function_does_not_call_runtime(self) -> None:
        runtime = FakeRuntimeService()
        with patch.object(chat_orchestrator, "runtime_service", runtime):
            chat_orchestrator.propose_travel_tool(
                "旅行一覧を見せて",
                text_generator=json_generator(
                    {
                        "action": "tool_proposal",
                        "tool_id": "get_trips",
                        "arguments": {},
                        "confidence": "high",
                        "reply": "旅行一覧を取得します。",
                    }
                ),
            )

        self.assertEqual(runtime.calls, [])

    def test_handle_executes_get_trips_through_runtime(self) -> None:
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": [{"id": "trip-1"}]}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), {"total": 1.0}),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "旅行一覧を見せて", role="admin", debug=True
            )

        self.assertEqual(result["action"], "tool_result")
        self.assertEqual(result["result"], {"trips": [{"id": "trip-1"}]})
        self.assertEqual(
            runtime.calls,
            [
                {
                    "tool_id": "get_trips",
                    "params": {},
                    "confirmed": False,
                    "role": "admin",
                }
            ],
        )
        self.assertTrue(
            {"proposal_total", "runtime_execute", "total"}.issubset(
                result["debug"]["timings_ms"]
            )
        )

    def test_named_trip_executes_get_trips_then_get_trip(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "福岡旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "福岡旅行を開いて", role="family", debug=True
            )

        self.assertEqual(result["action"], "tool_result")
        self.assertEqual(result["tool_id"], "get_trip")
        self.assertEqual(result["arguments"], {"trip_id": "trip-fukuoka"})
        self.assertEqual(result["reply"], "福岡旅行を開きます。")
        self.assertEqual(result["result"], {"trip": trip})
        self.assertEqual(
            result["navigation"],
            {
                "type": "travel_trip",
                "target": "#travel?trip_id=trip-fukuoka",
                "trip_id": "trip-fukuoka",
                "label": "Travelで開く",
            },
        )
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip"],
        )
        self.assertEqual(
            [step["tool_id"] for step in result["debug"]["steps"]],
            ["get_trips", "get_trip"],
        )
        self.assertEqual(
            result["debug"]["entity_resolution"],
            {
                "resolver": "travel_entity_resolver",
                "resolution_status": "resolved",
                "candidate_count": 1,
                "top_candidate_score": 1.0,
            },
        )
        self.assertEqual(
            result["updated_context"],
            {
                "selected_trip_id": "trip-fukuoka",
                "selected_trip_title": "福岡旅行",
            },
        )
        self.assertTrue(
            all(call["confirmed"] is False for call in runtime.calls)
        )

    def test_kobe_trip_query_opens_suma_trip_via_travel_search_index(self) -> None:
        trip = {
            "id": "trip-suma",
            "title": "須磨シーワールド",
            "prefectures": "兵庫県",
        }
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "神戸旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("神戸旅行を開いて")

        self.assertEqual(result["action"], "tool_result")
        self.assertEqual(result["arguments"], {"trip_id": "trip-suma"})
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip"],
        )

    def test_suma_query_opens_suma_trip(self) -> None:
        trip = {"id": "trip-suma", "title": "須磨シーワールド"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "須磨を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("須磨を開いて")

        self.assertEqual(result["tool_id"], "get_trip")
        self.assertEqual(result["navigation"]["trip_id"], "trip-suma")

    def test_prefecture_query_with_multiple_trips_does_not_auto_select(self) -> None:
        trips = [
            {
                "id": "trip-suma",
                "title": "須磨シーワールド",
                "prefectures": "兵庫県",
            },
            {
                "id": "trip-awaji",
                "title": "淡路島旅行",
                "prefectures": "兵庫県",
            },
        ]
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": trips}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "兵庫の旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("兵庫の旅行見せて")

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(result["reply"], "2件の候補があります。どれを開きますか？")
        self.assertEqual(
            {trip["id"] for trip in result["candidates"]},
            {"trip-suma", "trip-awaji"},
        )
        self.assertEqual([call["tool_id"] for call in runtime.calls], ["get_trips"])

    def test_selected_trip_detail_uses_context_id_not_model_id(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trip": trip}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trip",
            "arguments": {"trip_id": "trip-invented-by-model"},
            "confidence": "high",
            "reply": "旅行を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "この旅行の詳細見せて",
                context={
                    "selected_trip_id": "trip-fukuoka",
                    "selected_trip_title": "untrusted title",
                },
            )

        self.assertEqual(result["tool_id"], "get_trip")
        self.assertEqual(result["arguments"], {"trip_id": "trip-fukuoka"})
        self.assertEqual(runtime.calls[0]["params"], {"trip_id": "trip-fukuoka"})
        self.assertEqual(result["updated_context"]["selected_trip_title"], "福岡旅行")

    def test_selected_trip_day_uses_validated_context_for_timeline(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trip": trip}},
                {
                    "success": True,
                    "result": {"trip_id": "trip-fukuoka", "timeline": []},
                },
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trip_timeline",
            "arguments": {"trip_id": "trip-invented-by-model"},
            "confidence": "high",
            "reply": "日程を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "2日目は？",
                context={"selected_trip_id": "trip-fukuoka"},
                debug=True,
            )

        self.assertEqual(result["tool_id"], "get_trip_timeline")
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trip", "get_trip_timeline"],
        )
        self.assertTrue(
            all(call["params"] == {"trip_id": "trip-fukuoka"} for call in runtime.calls)
        )
        self.assertEqual(result["updated_context"]["selected_trip_title"], "福岡旅行")

    def test_invalid_selected_trip_is_cleared_without_timeline_call(self) -> None:
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trip": None}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trip_timeline",
            "arguments": {"trip_id": "missing-trip"},
            "confidence": "high",
            "reply": "日程を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "2日目は？",
                context={"selected_trip_id": "missing-trip"},
            )

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(result["updated_context"], {})
        self.assertEqual([call["tool_id"] for call in runtime.calls], ["get_trip"])

    def test_trip_list_preserves_context_without_validating_or_replacing_it(self) -> None:
        context = {
            "selected_trip_id": "trip-fukuoka",
            "selected_trip_title": "福岡旅行",
        }
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": []}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "旅行一覧を見せて", context=context
            )

        self.assertEqual(result["updated_context"], context)
        self.assertEqual([call["tool_id"] for call in runtime.calls], ["get_trips"])

    def test_opening_another_named_trip_replaces_selected_context(self) -> None:
        trip = {"id": "trip-osaka", "title": "大阪旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "大阪旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "大阪旅行を開いて",
                context={
                    "selected_trip_id": "trip-fukuoka",
                    "selected_trip_title": "福岡旅行",
                },
            )

        self.assertEqual(
            result["updated_context"],
            {
                "selected_trip_id": "trip-osaka",
                "selected_trip_title": "大阪旅行",
            },
        )

    def test_llm_context_and_authorization_fields_are_not_adopted(self) -> None:
        runtime = FakeRuntimeService()
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trip",
            "arguments": {"trip_id": "trip-fukuoka"},
            "confidence": "high",
            "reply": "旅行を取得します。",
            "context": {"selected_trip_id": "trip-attacker"},
            "role": "admin",
            "confirmed": True,
            "user_id": "attacker",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat(
                "この旅行の詳細見せて",
                context={"selected_trip_id": "trip-fukuoka"},
            )

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(
            result["updated_context"], {"selected_trip_id": "trip-fukuoka"}
        )
        self.assertEqual(runtime.calls, [])

    def test_named_trip_not_found_returns_safe_response(self) -> None:
        runtime = FakeRuntimeService(
            response={
                "success": True,
                "result": {"trips": [{"id": "trip-osaka", "title": "大阪旅行"}]},
            }
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("福岡旅行を開いて")

        self.assertEqual(
            result,
            {
                "action": "needs_context",
                "reply": "該当する旅行が見つかりませんでした。",
            },
        )
        self.assertEqual(len(runtime.calls), 1)

    def test_trip_navigation_url_encodes_resolved_id(self) -> None:
        result = chat_orchestrator._runtime_success_result(
            "get_trip",
            {"trip_id": "trip/fukuoka 2026?draft"},
            {"trip": {"id": "trip/fukuoka 2026?draft", "title": "福岡旅行"}},
        )

        self.assertEqual(
            result["navigation"]["target"],
            "#travel?trip_id=trip%2Ffukuoka%202026%3Fdraft",
        )
        self.assertEqual(
            result["navigation"]["trip_id"], "trip/fukuoka 2026?draft"
        )

    def test_multiple_named_trip_candidates_are_not_auto_selected(self) -> None:
        trips = [
            {"id": "trip-1", "title": "大阪旅行 2025"},
            {"id": "trip-2", "title": "大阪旅行 2026"},
        ]
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": trips}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "大阪旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("大阪旅行を開いて")

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(result["reply"], "2件の候補があります。どれを開きますか？")
        self.assertEqual(result["candidates"], trips)
        self.assertEqual(len(runtime.calls), 1)

    def test_candidate_clarification_reply_is_generated_by_final_answer_llm(self) -> None:
        trips = [
            {"id": "trip-1", "title": "大阪旅行 2025"},
            {"id": "trip-2", "title": "大阪旅行 2026"},
        ]
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": trips}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "大阪旅行を探します。",
        }

        result = chat_orchestrator.handle_travel_chat(
            "大阪旅行を開いて",
            debug=True,
            text_generator=json_generator(proposal),
            final_answer_text_generator=lambda **_: (
                "大阪旅行は2025年と2026年の2件あります。どちらにしますか？",
                None,
            ),
            runtime=runtime,
        )

        self.assertEqual(
            result["reply"],
            "大阪旅行は2025年と2026年の2件あります。どちらにしますか？",
        )
        self.assertEqual(result["debug"]["final_answer_source"], "llm")
        self.assertEqual(result["clarification"]["clarification"], result["reply"])

    def test_max_steps_stops_before_follow_up_runtime_call(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response={"success": True, "result": {"trips": [trip]}}
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "福岡旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
            patch.object(chat_orchestrator, "MAX_TRAVEL_STEPS", 1),
        ):
            result = chat_orchestrator.handle_travel_chat("福岡旅行を開いて")

        self.assertEqual(result["action"], "needs_context")
        self.assertIn("安全のため", result["reply"])
        self.assertEqual(len(runtime.calls), 1)

    def test_trip_name_normalization_supports_width_case_and_spaces(self) -> None:
        result = chat_orchestrator._find_trip_candidates(
            {"trips": [{"id": "trip-1", "title": "ＦＵＫＵＯＫＡ 旅行"}]},
            chat_orchestrator._extract_trip_name("fukuokaを開いて"),
        )

        self.assertEqual([trip["id"] for trip in result], ["trip-1"])

    def test_read_tool_outside_allowlist_is_not_executed(self) -> None:
        runtime = FakeRuntimeService()
        invalid_proposal = {
            "action": "tool_proposal",
            "tool_id": "get_spots",
            "arguments": {},
            "confidence": "high",
            "reply": "場所を取得します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(invalid_proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("場所を見せて")

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(runtime.calls, [])

    def test_update_experience_is_not_executed(self) -> None:
        runtime = FakeRuntimeService()
        proposal = {
            "action": "tool_proposal",
            "tool_id": "update_experience",
            "arguments": {"experience_id": "experience-1", "memo": "更新"},
            "confidence": "high",
            "reply": "体験を更新します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("メモを更新して")

        self.assertEqual(result["action"], "pending_write_not_implemented")
        self.assertEqual(runtime.calls, [])

    def test_llm_authorization_fields_are_rejected(self) -> None:
        runtime = FakeRuntimeService()
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
            "role": "admin",
            "confirmed": True,
            "user_id": "user-1",
            "navigation": {"target": "https://example.invalid"},
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("旅行一覧を見せて")

        self.assertEqual(result["action"], "needs_context")
        self.assertEqual(runtime.calls, [])

    def test_guest_cannot_execute_medium_risk_photo_read(self) -> None:
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_experience_photos",
            "arguments": {"experience_id": "experience-1"},
            "confidence": "high",
            "reply": "写真を取得します。",
        }

        with patch.object(
            chat_orchestrator,
            "generate_text_with_timings",
            return_value=(json.dumps(proposal), None),
        ):
            result = chat_orchestrator.handle_travel_chat("写真を見せて", role="guest")

        self.assertEqual(result["action"], "permission_denied")
        self.assertNotIn("result", result)

    def test_runtime_exception_and_result_secrets_are_not_exposed(self) -> None:
        secret = "sk-runtime-secret-value"
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "旅行一覧を取得します。",
        }
        error_runtime = FakeRuntimeService(error=RuntimeError(f"Bearer {secret}"))

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", error_runtime),
        ):
            error_result = chat_orchestrator.handle_travel_chat("旅行一覧を見せて")

        secret_runtime = FakeRuntimeService(
            response={"success": True, "result": {"value": f"Bearer {secret}"}}
        )
        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", secret_runtime),
        ):
            success_result = chat_orchestrator.handle_travel_chat("旅行一覧を見せて")

        self.assertEqual(error_result["action"], "runtime_error")
        self.assertNotIn(secret, json.dumps(error_result))
        self.assertNotIn(secret, json.dumps(success_result))

    def test_resolved_trip_id_secret_is_redacted_from_arguments_and_navigation(self) -> None:
        secret = "sk-resolved-trip-secret"
        trip = {"id": f"Bearer {secret}", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "福岡旅行を探します。",
        }

        with (
            patch.object(
                chat_orchestrator,
                "generate_text_with_timings",
                return_value=(json.dumps(proposal), None),
            ),
            patch.object(chat_orchestrator, "runtime_service", runtime),
        ):
            result = chat_orchestrator.handle_travel_chat("福岡旅行を開いて")

        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))

    def test_chat_tool_policy_separates_read_and_write(self) -> None:
        self.assertEqual(
            CHAT_READ_EXECUTABLE_TOOLS | CHAT_WRITE_PENDING_TOOLS,
            CHAT_TRAVEL_TOOL_ALLOWLIST,
        )
        self.assertEqual(
            get_chat_tool_execution_policy("get_trips"), "read_executable"
        )
        self.assertEqual(
            get_chat_tool_execution_policy("update_experience"),
            "write_requires_pending_action",
        )

    def test_named_trip_activity_question_returns_answer_from_acquired_evidence(self) -> None:
        trip = {
            "id": "trip-kobe",
            "title": "神戸旅行",
            "start_date": "2026-06-01",
        }
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {
                    "success": True,
                    "result": {
                        "trip_id": "trip-kobe",
                        "items": [
                            {"display_title": "須磨シーワールド"},
                            {"display_title": "ホテル"},
                        ],
                    },
                },
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "medium",
            "reply": "神戸旅行を探します。",
        }

        result = chat_orchestrator.handle_travel_chat(
            "神戸旅行で何した？",
            debug=True,
            text_generator=json_generator(proposal),
            final_answer_text_generator=lambda **_: (
                "神戸旅行では、須磨シーワールド、その後ホテルの記録があります。",
                None,
            ),
            runtime=runtime,
        )

        self.assertEqual(result["action"], "tool_result")
        self.assertEqual(result["tool_id"], "get_trip_timeline")
        self.assertEqual(
            result["reply"],
            "神戸旅行では、須磨シーワールド、その後ホテルの記録があります。",
        )
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip_timeline"],
        )
        self.assertEqual(
            result["debug"]["answer_generation"],
            {
                "answer_type": "grounded",
                "confidence": "high",
                "used_evidence_count": 2,
                "evidence_used": True,
                "final_answer_source": "llm",
                "final_answer_fallback_reason": None,
            },
        )

    def test_named_trip_answer_uses_llm_after_runtime_evidence(self) -> None:
        trips = [{"id": "trip-fukuoka", "title": "福岡旅行"}]
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": trips}},
                {
                    "success": True,
                    "result": {
                        "trip_id": "trip-fukuoka",
                        "timeline": [
                            {"title": "屋台でラーメン", "category": "food"}
                        ],
                    },
                },
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "福岡旅行を探します。",
            "goal": "summarize_meals",
            "answer_mode": "meals",
            "required_evidence": ["trip", "timeline"],
            "entity_query": "福岡旅行",
        }
        captured = {}

        def final_generator(**kwargs):
            captured.update(kwargs)
            return "福岡旅行では、屋台でラーメンを食べた記録があります。", None

        result = chat_orchestrator.handle_travel_chat(
            "福岡旅行のご飯何食べた？",
            debug=True,
            text_generator=json_generator(proposal),
            final_answer_text_generator=final_generator,
            runtime=runtime,
        )

        self.assertEqual(
            result["reply"],
            "福岡旅行では、屋台でラーメンを食べた記録があります。",
        )
        self.assertEqual(result["debug"]["route"], "travel")
        self.assertTrue(result["debug"]["evidence_used"])
        self.assertEqual(result["debug"]["final_answer_source"], "llm")
        self.assertIsNone(result["debug"]["final_answer_fallback_reason"])
        self.assertIn("屋台でラーメン", captured["input_text"])
        self.assertNotIn('"trips"', captured["input_text"])
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip_timeline"],
        )

    def test_final_answer_failure_does_not_reinterpret_question_in_python(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            response=[
                {"success": True, "result": {"trips": [trip]}},
                {
                    "success": True,
                    "result": {"timeline": [{"title": "屋台でラーメン"}]},
                },
            ]
        )
        proposal = {
            "action": "tool_proposal",
            "tool_id": "get_trips",
            "arguments": {},
            "confidence": "high",
            "reply": "福岡旅行を探します。",
            "goal": "summarize_meals",
            "answer_mode": "meals",
            "required_evidence": ["trip", "timeline"],
            "entity_query": "福岡旅行",
        }

        result = chat_orchestrator.handle_travel_chat(
            "福岡旅行のご飯何食べた？",
            debug=True,
            text_generator=json_generator(proposal),
            final_answer_text_generator=lambda **_: (_ for _ in ()).throw(
                RuntimeError("unavailable")
            ),
            runtime=runtime,
        )

        self.assertEqual(result["reply"], "旅行タイムラインを取得しました。")
        self.assertEqual(
            result["debug"]["final_answer_source"],
            "fallback_static",
        )
        self.assertEqual(
            result["debug"]["final_answer_fallback_reason"],
            "final answer LLM failed",
        )


if __name__ == "__main__":
    unittest.main()
