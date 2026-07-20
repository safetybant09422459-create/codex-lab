import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from backend import openai_adapter
from backend.agent_host import LLMInputPayload, Principal
from backend.provider_registry import ProviderRegistry
from backend.travel_executor import TravelProvider
from backend.observation import ObservationEnvelope
from backend.photo_executor import PhotoProvider
from backend.gift_executor import GiftProvider
from backend.jarvis_provider import JarvisProvider
from backend.chat_trace import ChatTraceRecorder, ChatTraceStore


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": "OK\n"})()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class OpenAIAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        openai_adapter._client = None

    def tearDown(self) -> None:
        openai_adapter._client = None

    @staticmethod
    def current_catalog() -> dict[str, object]:
        registry = ProviderRegistry()
        registry.register(TravelProvider())
        registry.register(PhotoProvider())
        registry.register(GiftProvider(repository=object()))
        registry.register(JarvisProvider(registry.catalog, registry.capability_catalog))
        return registry.catalog()

    @staticmethod
    def action_payload() -> LLMInputPayload:
        return LLMInputPayload(
            turn_id="turn-1",
            session_id="session-1",
            principal=Principal(role="guest"),
            channel="chat",
            normalized_input={"text": "旅行一覧を見せて"},
            conversation_context=[],
            conversation_state={},
            persona_context={},
            memory_context=[],
            activation_candidates=[],
            available_operations={"contract_version": "1", "providers": []},
            runtime_policy={"max_steps": 2},
            prior_observations=[],
        )

    @staticmethod
    def answer_action() -> dict[str, object]:
        return {
            "contract_version": "1",
            "action": "answer",
            "message": "了解しました。",
            "conversation_update": {
                "transition": "start_request",
                "current_topic": None,
                "previous_topic": None,
                "active_entities": None,
                "pending_question": None,
                "unresolved_intent": None,
            },
        }

    @classmethod
    def structured_answer(cls) -> str:
        return json.dumps({"llm_action": cls.answer_action()})

    @classmethod
    def native_answer(cls) -> object:
        action = cls.answer_action()
        values = {
            "message": action["message"],
            "conversation_update": {
                key: value
                for key, value in action["conversation_update"].items()
                if key != "active_entities"
            },
        }
        return SimpleNamespace(
            output_text="",
            output=[SimpleNamespace(
                type="function_call",
                name="jarvis_control_answer",
                arguments=json.dumps(values),
            )],
        )

    def assert_schema_has_no_references(self, node: object) -> None:
        if isinstance(node, dict):
            self.assertNotIn("$ref", node)
            self.assertNotIn("$defs", node)
            self.assertNotIn("definitions", node)
            for value in node.values():
                self.assert_schema_has_no_references(value)
        elif isinstance(node, list):
            for value in node:
                self.assert_schema_has_no_references(value)

    def assert_all_object_schemas_are_strict(self, node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                self.assertIs(
                    node.get("additionalProperties"),
                    False,
                    msg=f"Object schema is not closed: {node}",
                )
                properties = node.get("properties")
                self.assertIsInstance(properties, dict)
                self.assertEqual(
                    node.get("required"),
                    list(properties),
                    msg=f"Object required keys do not match properties: {node}",
                )
            for value in node.values():
                self.assert_all_object_schemas_are_strict(value)
        elif isinstance(node, list):
            for value in node:
                self.assert_all_object_schemas_are_strict(value)

    @staticmethod
    def action_schema_branches() -> list[dict[str, object]]:
        schema = openai_adapter._action_output_schema()
        return schema["properties"]["llm_action"]["anyOf"]

    def test_llm_client_request_contains_contract_payload_and_schema(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **kwargs: (
            client.responses.calls.append(kwargs)
            or self.native_answer()
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                self.action_payload()
            )

        request = client.responses.calls[0]
        sent_payload = json.loads(str(request["input"]))
        self.assertEqual(sent_payload["contract_version"], "1")
        self.assertEqual(sent_payload["normalized_input"]["text"], "旅行一覧を見せて")
        self.assertEqual(request["model"], "test-model")
        self.assertFalse(request["store"])
        self.assertEqual(request["tool_choice"], "required")
        self.assertEqual(len(request["tools"]), 4)
        self.assertNotIn("format", request["text"])
        self.assertNotIn("test-secret", repr(request))
        self.assertEqual(result["action"], "answer")

    def test_first_request_has_operation_and_four_control_tools(self) -> None:
        payload = self.action_payload()
        payload.available_operations = self.current_catalog()
        request, registry = openai_adapter._build_action_request_with_registry(payload)

        names = {tool["name"] for tool in request["tools"]}
        controls = {
            "jarvis_control_answer",
            "jarvis_control_ask_clarification",
            "jarvis_control_request_confirmation",
            "jarvis_control_refuse",
        }
        self.assertTrue(registry.entries)
        self.assertEqual(names, controls | set(registry.entries))
        sent_payload = json.loads(request["input"])
        operation_index = sent_payload["available_operations"]
        self.assertTrue(operation_index["providers"])
        serialized_index = json.dumps(operation_index)
        self.assertNotIn('"input_schema"', serialized_index)
        self.assertNotIn('"output_schema"', serialized_index)
        self.assertNotIn('"examples"', serialized_index)
        indexed = operation_index["providers"][0]["operations"][0]
        self.assertIn("operation_id", indexed)
        self.assertIn("description", indexed)
        self.assertIn("availability", indexed)
        self.assertIn("risk_level", indexed)
        self.assertIn("confirmation_required", indexed)
        self.assertIn("what_it_can_do", indexed)
        self.assertIn("what_it_cannot_do", indexed)
        self.assertIn("limitations", indexed)
        native_operation = next(
            tool for tool in request["tools"] if tool["name"] in registry.entries
        )
        registry_entry = registry.entries[native_operation["name"]]
        self.assertEqual(
            native_operation["parameters"]["properties"]["arguments"],
            registry_entry.openai_schema,
        )

    def test_request_after_observation_has_only_four_control_tools(self) -> None:
        payload = self.action_payload()
        payload.available_operations = self.current_catalog()
        payload.prior_observations = [ObservationEnvelope(
            provider_id="travel", operation_id="get_trips", status="success",
            raw_result={"success": True}, facts={},
            provenance={"provider_id": "travel", "operation_id": "get_trips"},
            observed_at="2026-07-19T00:00:00+00:00",
        )]
        request, registry = openai_adapter._build_action_request_with_registry(payload)

        self.assertTrue(registry.entries)
        self.assertEqual(
            {tool["name"] for tool in request["tools"]},
            {
                "jarvis_control_answer",
                "jarvis_control_ask_clarification",
                "jarvis_control_request_confirmation",
                "jarvis_control_refuse",
            },
        )
        sent_payload = json.loads(request["input"])
        self.assertNotIn("available_operations", sent_payload)
        self.assertEqual(len(sent_payload["prior_observations"]), 1)
        self.assertNotIn('"input_schema"', request["input"])
        self.assertNotIn('"output_schema"', request["input"])
        self.assertNotIn('"what_it_can_do"', request["input"])
        self.assertNotIn('"what_it_cannot_do"', request["input"])
        self.assertNotIn("Display or choose photos", request["input"])

    def test_compact_index_preserves_boundaries_without_mutating_catalog(self) -> None:
        catalog = {
            "contract_version": "1",
            "providers": [{
                "provider_id": "photo",
                "operations": [{
                    "provider_id": "photo",
                    "operation_id": "get_recent_photos",
                    "description": "Get recent photo metadata",
                    "availability": "implemented",
                    "risk_level": "low",
                    "confirmation_required": False,
                    "what_it_can_do": "Summarize recent photo metadata.",
                    "what_it_cannot_do": "Display or choose photos.",
                    "limitations": ["Metadata only."],
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object"},
                    "examples": [{"request": "Show photos"}],
                    "implementation_metadata": "x" * 1000,
                }],
            }],
        }
        original = deepcopy(catalog)

        index = openai_adapter._compact_operation_index(catalog)
        operation = index["providers"][0]["operations"][0]

        self.assertEqual(operation["what_it_can_do"], "Summarize recent photo metadata.")
        self.assertEqual(operation["what_it_cannot_do"], "Display or choose photos.")
        self.assertEqual(operation["limitations"], ["Metadata only."])
        for excluded in (
            "input_schema", "output_schema", "examples", "implementation_metadata"
        ):
            self.assertNotIn(excluded, operation)
        self.assertEqual(catalog, original)

    def test_action_instructions_prefer_answer_without_required_operation(self) -> None:
        instructions = openai_adapter._build_action_request(
            self.action_payload()
        )["instructions"]

        self.assertIn("Use an operation only when", instructions)
        self.assertIn("conversation context alone is enough", instructions)
        self.assertIn("If no operation is needed, choose answer", instructions)
        self.assertIn("Greetings", instructions)
        self.assertIn("get_capabilities", instructions)
        self.assertIn("get_provider_status", instructions)
        self.assertIn("get_operation_catalog", instructions)
        self.assertIn("self-diagnostic operations", instructions)
        self.assertIn("preflight", instructions)
        self.assertIn("just-in-case check", instructions)
        self.assertIn("preparation for a normal answer", instructions)
        self.assertIn("conversation context alone can answer", instructions)
        self.assertIn("prior observation", instructions)

    def test_compact_index_preserves_declarative_jarvis_metadata(self) -> None:
        index = openai_adapter._compact_operation_index(self.current_catalog())
        jarvis = next(
            provider for provider in index["providers"]
            if provider["provider_id"] == "jarvis"
        )
        operations = {
            operation["operation_id"]: operation
            for operation in jarvis["operations"]
        }

        self.assertEqual(
            set(operations),
            {"get_capabilities", "get_provider_status", "get_operation_catalog"},
        )
        self.assertIn(
            "Capability Catalog", operations["get_capabilities"]["limitations"][0]
        )
        self.assertIn(
            "Capability Catalog", operations["get_provider_status"]["limitations"][0]
        )
        self.assertIn(
            "local catalog", operations["get_operation_catalog"]["limitations"][0]
        )
        serialized = json.dumps(jarvis, ensure_ascii=False).lower()
        for routing_phrase in (
            "use only when",
            "user asks",
            "greetings",
            "general conversation",
            "preflight",
            "just-in-case",
            "preparation for",
        ):
            self.assertNotIn(routing_phrase, serialized)

    def test_trace_uses_the_actual_projected_request_input(self) -> None:
        store = ChatTraceStore()
        recorder = ChatTraceRecorder(store, {})
        recorder.start_turn("turn-1", "session-1", {"text": "hello"})
        client = FakeClient()
        client.responses.create = lambda **kwargs: (
            client.responses.calls.append(kwargs) or self.native_answer()
        )
        first_payload = self.action_payload()
        first_payload.available_operations = self.current_catalog()
        second_payload = first_payload.model_copy(deep=True)
        second_payload.prior_observations = [ObservationEnvelope(
            provider_id="travel", operation_id="get_trips", status="success",
            raw_result={"success": True}, facts={"trip_count": 0},
            provenance={"provider_id": "travel", "operation_id": "get_trips"},
            observed_at="2026-07-19T00:00:00+00:00",
        )]

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            adapter = openai_adapter.OpenAIModelProviderAdapter(recorder)
            adapter.complete(first_payload)
            adapter.complete(second_payload)

        calls = store.get("turn-1")["llm_calls"]
        for call, sent_request in zip(calls, client.responses.calls):
            traced = call["request"]
            self.assertEqual(
                traced["input_payload_bytes"],
                len(sent_request["input"].encode("utf-8")),
            )
        first_request, second_request = (call["request"] for call in calls)
        self.assertTrue(first_request["operation_catalog_present"])
        first_sent_payload = json.loads(client.responses.calls[0]["input"])
        self.assertEqual(
            first_request["available_operations_bytes"],
            len(json.dumps(
                first_sent_payload["available_operations"], ensure_ascii=False
            ).encode("utf-8")),
        )
        self.assertFalse(second_request["operation_catalog_present"])
        self.assertEqual(second_request["available_operations_bytes"], 0)
        second_input = client.responses.calls[1]["input"]
        for operation_id in (
            "get_capabilities", "get_provider_status", "get_operation_catalog"
        ):
            self.assertNotIn(operation_id, second_input)

    def test_all_control_tools_normalize_to_common_actions(self) -> None:
        _request, registry = openai_adapter._build_action_request_with_registry(
            self.action_payload()
        )
        update = {
            "transition": "end_conversation", "current_topic": None,
            "previous_topic": None, "pending_question": None,
            "unresolved_intent": None,
        }
        for action in ("answer", "ask_clarification", "request_confirmation", "refuse"):
            with self.subTest(action=action):
                response = SimpleNamespace(output=[SimpleNamespace(
                    type="function_call", name=f"jarvis_control_{action}",
                    arguments=json.dumps({"message": "message", "conversation_update": update}),
                )])
                normalized = openai_adapter._normalize_native_tool_response(response, registry)
                self.assertEqual(normalized["action"], action)

    def test_operation_arguments_normalize_without_semantic_change(self) -> None:
        payload = self.action_payload()
        payload.available_operations = {
            "providers": [{"provider_id": "travel", "operations": [{
                "provider_id": "travel", "operation_id": "get_trip",
                "availability": "implemented", "description": "Get trip",
                "input_schema": {
                    "type": "object", "properties": {
                        "trip_id": {"type": "string"},
                        "optional_note": {"type": "string"},
                    }, "required": ["trip_id"],
                },
            }]}],
        }
        _request, registry = openai_adapter._build_action_request_with_registry(payload)
        response = SimpleNamespace(output=[SimpleNamespace(
            type="function_call", name="jarvis__travel__get_trip",
            arguments=json.dumps({
                "arguments": {"trip_id": "trip-1", "optional_note": None},
                "conversation_update": {
                    "transition": "continue_unresolved_intent", "current_topic": None,
                    "previous_topic": None, "pending_question": None,
                    "unresolved_intent": None,
                },
            }),
        )])

        normalized = openai_adapter._normalize_native_tool_response(response, registry)
        self.assertEqual(normalized["provider_id"], "travel")
        self.assertEqual(normalized["operation_id"], "get_trip")
        self.assertEqual(normalized["arguments"], {"trip_id": "trip-1"})

    def test_invalid_native_tool_names_and_arguments_fail_closed(self) -> None:
        payload = self.action_payload()
        payload.available_operations = self.current_catalog()
        _request, registry = openai_adapter._build_action_request_with_registry(payload)
        update = {
            "transition": "start_request", "current_topic": None,
            "previous_topic": None, "pending_question": None,
            "unresolved_intent": None,
        }
        invalid_calls = [
            SimpleNamespace(type="function_call", name="unknown", arguments="{}"),
            SimpleNamespace(type="function_call", name="jarvis_control_answer", arguments="{"),
            SimpleNamespace(
                type="function_call", name="jarvis_control_answer",
                arguments=json.dumps({
                    "message": "message", "conversation_update": update,
                    "unexpected": True,
                }),
            ),
        ]
        operation = next(iter(registry.entries.values()))
        invalid_calls.append(SimpleNamespace(
            type="function_call", name=operation.name,
            arguments=json.dumps({"arguments": {"unexpected": True}, "conversation_update": update}),
        ))
        for call in invalid_calls:
            with self.subTest(name=call.name):
                with self.assertRaises(openai_adapter.OpenAIResponseValidationError):
                    openai_adapter._normalize_native_tool_response(
                        SimpleNamespace(output=[call]), registry
                    )

    def test_action_output_schema_is_self_contained(self) -> None:
        self.assert_schema_has_no_references(openai_adapter._action_output_schema())

    def test_action_output_schema_normalizes_every_object(self) -> None:
        self.assert_all_object_schemas_are_strict(
            openai_adapter._action_output_schema()
        )

    def test_strict_schema_closes_nested_array_and_any_of_objects(self) -> None:
        schema = openai_adapter._strict_json_schema(
            {
                "type": "object",
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["missing"],
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "object", "properties": {}},
                    },
                    "choice": {
                        "anyOf": [
                            {"type": "object", "properties": {}},
                            {"type": "null"},
                        ]
                    },
                },
            }
        )

        self.assert_all_object_schemas_are_strict(schema)

    def test_answer_action_is_represented_and_rejects_hidden_fields(self) -> None:
        message_branch = next(
            branch
            for branch in self.action_schema_branches()
            if "answer" in branch["properties"]["action"].get("enum", [])
        )

        self.assertIn("message", message_branch["required"])
        self.assertIn("conversation_update", message_branch["required"])
        self.assertFalse(message_branch["additionalProperties"])
        self.assertNotIn("reasoning", message_branch["properties"])
        self.assertNotIn("analysis", message_branch["properties"])
        self.assertNotIn("hidden_thought", message_branch["properties"])

    def test_output_schema_represents_all_llm_actions(self) -> None:
        represented: set[str] = set()
        for branch in self.action_schema_branches():
            action_schema = branch["properties"]["action"]
            if "const" in action_schema:
                represented.add(action_schema["const"])
            represented.update(action_schema.get("enum", []))

        self.assertEqual(
            represented,
            {
                "answer",
                "ask_clarification",
                "call_operation",
                "request_confirmation",
                "refuse",
            },
        )

    def test_call_operation_action_is_represented_in_output_schema(self) -> None:
        operation_branch = next(
            branch
            for branch in self.action_schema_branches()
            if branch["properties"]["action"].get("const") == "call_operation"
        )

        self.assertEqual(
            set(operation_branch["required"]),
            {
                "contract_version",
                "action",
                "provider_id",
                "operation_id",
                "arguments",
                "conversation_update",
            },
        )
        self.assertFalse(operation_branch["additionalProperties"])
        arguments_schema = operation_branch["properties"]["arguments"]
        self.assertEqual(arguments_schema["properties"], {})
        self.assertEqual(arguments_schema["required"], [])

    def test_call_operation_action_is_returned_without_semantic_changes(self) -> None:
        client = FakeClient()
        action = {
            "contract_version": "1",
            "action": "call_operation",
            "provider_id": "travel",
            "operation_id": "get_trips",
            "arguments": {},
            "conversation_update": {
                "transition": "continue_unresolved_intent",
                "current_topic": None,
                "previous_topic": None,
                "active_entities": None,
                "pending_question": None,
                "unresolved_intent": None,
            },
        }
        registry_payload = self.action_payload()
        registry_payload.available_operations = {
            "contract_version": "1",
            "providers": [{"provider_id": "travel", "operations": [{
                "provider_id": "travel", "operation_id": "get_trips",
                "availability": "implemented", "description": "List trips",
                "input_schema": {"type": "object", "properties": {}},
            }]}],
        }
        client.responses.create = lambda **_kwargs: SimpleNamespace(output=[
            SimpleNamespace(
                type="function_call", name="jarvis__travel__get_trips",
                arguments=json.dumps({
                    "arguments": {},
                    "conversation_update": {
                        key: value for key, value in action["conversation_update"].items()
                        if key != "active_entities"
                    },
                }),
            )
        ])

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                registry_payload
            )

        self.assertEqual(result, action)

    def test_provider_reasoning_item_is_not_returned_or_saved(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=[
                SimpleNamespace(type="reasoning", content="hidden thought"),
                *self.native_answer().output,
            ],
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.OpenAIModelProviderAdapter().complete(
                self.action_payload()
            )

        self.assertNotIn("reasoning", result)
        self.assertNotIn("hidden thought", repr(result))

    def test_invalid_structured_action_raises_validation_error(self) -> None:
        client = FakeClient()
        invalid = self.answer_action()
        invalid["reasoning"] = "must not enter the contract"
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text=json.dumps({"llm_action": invalid})
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            with self.assertRaises(openai_adapter.OpenAIResponseValidationError):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_action_request_timeout_has_distinct_error(self) -> None:
        client = FakeClient()

        class APITimeoutError(Exception):
            pass

        client.responses.create = lambda **_kwargs: (_ for _ in ()).throw(
            APITimeoutError("request timed out")
        )
        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            with self.assertRaises(openai_adapter.OpenAITimeoutError):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_action_incomplete_response_has_distinct_error(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=[],
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            with self.assertRaisesRegex(
                openai_adapter.OpenAIIncompleteResponseError,
                "max_output_tokens",
            ):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_action_refusal_has_distinct_error_without_refusal_text(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            status="completed",
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            type="refusal",
                            refusal="provider refusal detail",
                        )
                    ]
                )
            ],
        )
        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            with self.assertRaises(
                openai_adapter.OpenAIModelRefusalError
            ) as context:
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

        self.assertNotIn("provider refusal detail", str(context.exception))

    def test_llm_client_error_redacts_api_key(self) -> None:
        api_key = "sk-adapter-super-secret"
        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"Bearer {api_key}"),
            ),
        ):
            with self.assertRaises(openai_adapter.OpenAIRequestError) as context:
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

        self.assertNotIn(api_key, str(context.exception))

    def test_llm_client_without_api_key_fails_before_request(self) -> None:
        with patch.object(openai_adapter, "OPENAI_API_KEY", ""):
            with self.assertRaisesRegex(
                openai_adapter.OpenAIConfigurationError, "OPENAI_API_KEY"
            ):
                openai_adapter.OpenAIModelProviderAdapter().complete(
                    self.action_payload()
                )

    def test_generate_text_reuses_client_within_process(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter, "_create_client", return_value=client
            ) as create_client,
        ):
            for _ in range(2):
                openai_adapter.generate_text(
                    instructions="Return JSON.",
                    input_text="旅行一覧を見せて",
                )

        create_client.assert_called_once_with()
        self.assertEqual(len(client.responses.calls), 2)

    def test_generate_text_keeps_server_request_unstored(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.generate_text(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(result, "OK")
        self.assertEqual(
            client.responses.calls,
            [
                {
                    "model": "test-model",
                    "instructions": "Return JSON.",
                    "input": "旅行一覧を見せて",
                    "store": False,
                    "max_output_tokens": 256,
                }
            ],
        )

    def test_generate_text_applies_configured_inference_settings(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5.4-mini"),
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "192"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", "none"),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", "low"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            openai_adapter.generate_text(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(
            client.responses.calls[0],
            {
                "model": "gpt-5.4-mini",
                "instructions": "Return JSON.",
                "input": "旅行一覧を見せて",
                "store": False,
                "reasoning": {"effort": "none"},
                "text": {"verbosity": "low"},
                "max_output_tokens": 192,
            },
        )

    def test_unset_optional_settings_preserve_api_defaults(self) -> None:
        with (
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", ""),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
        ):
            settings = openai_adapter._inference_settings()

        self.assertEqual(settings, {"max_output_tokens": 256})

    def test_invalid_inference_setting_is_rejected_locally(self) -> None:
        with (
            patch.object(openai_adapter, "OPENAI_MAX_OUTPUT_TOKENS", "256"),
            patch.object(openai_adapter, "OPENAI_REASONING_EFFORT", "fastest"),
            patch.object(openai_adapter, "OPENAI_VERBOSITY", ""),
        ):
            with self.assertRaises(openai_adapter.OpenAIConfigurationError):
                openai_adapter._inference_settings()

    def test_generate_text_with_timings_returns_numeric_adapter_timings(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            text, timings = openai_adapter.generate_text_with_timings(
                instructions="Return JSON.",
                input_text="旅行一覧を見せて",
            )

        self.assertEqual(text, "OK")
        self.assertEqual(
            set(timings),
            {"api_call", "response_text_extraction", "total"},
        )
        self.assertTrue(
            all(isinstance(value, (int, float)) for value in timings.values())
        )

    def test_generate_text_error_does_not_expose_api_key(self) -> None:
        api_key = "sk-test-generate-secret"

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"invalid Bearer {api_key}"),
            ),
        ):
            with self.assertRaises(openai_adapter.OpenAIRequestError) as context:
                openai_adapter.generate_text(
                    instructions="Return JSON.",
                    input_text="旅行一覧を見せて",
                )

        self.assertNotIn(api_key, str(context.exception))

    def test_check_openai_connection_uses_server_configuration(self) -> None:
        client = FakeClient()

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "test-model"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(result, "OK")
        self.assertEqual(
            client.responses.calls,
            [
                {
                    "model": "test-model",
                    "input": "Reply with OK only.",
                    "store": False,
                }
            ],
        )

    def test_extracts_output_text_from_responses_api_items(self) -> None:
        response = SimpleNamespace(
            output_text="",
            output=[
                SimpleNamespace(type="reasoning", content=[]),
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", text="OK\n")],
                ),
            ],
        )
        client = FakeClient()
        client.responses.create = lambda **_kwargs: response

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(result, "OK")

    def test_missing_api_key_returns_actionable_message(self) -> None:
        with patch.object(openai_adapter, "OPENAI_API_KEY", ""):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(
            result,
            "OpenAI connection failed: OPENAI_API_KEY is not configured",
        )

    def test_api_error_returns_cause_without_exposing_api_key(self) -> None:
        api_key = "sk-test-secret-value"

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", api_key),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(
                openai_adapter,
                "_create_client",
                side_effect=RuntimeError(f"invalid API key: {api_key}"),
            ),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertIn("RuntimeError: invalid API key", result)
        self.assertNotIn(api_key, result)

    def test_empty_response_returns_response_diagnostics(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=[],
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertEqual(
            result,
            "OpenAI connection failed: response contained no text output "
            "(status=incomplete, reason=max_output_tokens)",
        )

    def test_malformed_response_returns_format_error(self) -> None:
        client = FakeClient()
        client.responses.create = lambda **_kwargs: SimpleNamespace(
            output_text="",
            output=object(),
        )

        with (
            patch.object(openai_adapter, "OPENAI_API_KEY", "test-secret"),
            patch.object(openai_adapter, "OPENAI_MODEL", "gpt-5"),
            patch.object(openai_adapter, "_create_client", return_value=client),
        ):
            result = openai_adapter.check_openai_connection()

        self.assertIn(
            "OpenAI connection failed: invalid Responses API response: TypeError",
            result,
        )


if __name__ == "__main__":
    unittest.main()
