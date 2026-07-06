import json
import unittest

from backend.conversation_context import (
    ContextAssemblyConfig,
    ConversationContextBuilder,
)
from backend.conversation_state import ConversationTurnState


def turn(index: int, **kwargs) -> ConversationTurnState:
    return ConversationTurnState(
        user_input={"text": f"user-{index}"},
        assistant_final_response=f"assistant-{index}",
        last_llm_action={"action": "answer", "index": index},
        **kwargs,
    )


class ConversationContextBuilderTest(unittest.TestCase):
    def build(self, builder=None, turns=(), capabilities=(), allowed=None):
        return (builder or ConversationContextBuilder()).build(
            session_id="session-1",
            channel="chat",
            conversation_started_at="2026-07-06T00:00:00+00:00",
            previous_turns=turns,
            capabilities=capabilities,
            allowed_visibilities=allowed or frozenset({"public", "family"}),
        )

    def test_context_order_is_deterministic_and_turn_limit_keeps_latest(self):
        result = self.build(
            ConversationContextBuilder(ContextAssemblyConfig(max_turns=2)),
            [turn(1), turn(2), turn(3)],
        )

        self.assertEqual(
            [
                item["user_input"]["text"]
                for item in result["conversation_context"]
            ],
            ["user-2", "user-3"],
        )
        self.assertEqual(result["conversation_state"]["last_llm_action"]["index"], 3)

    def test_latest_observations_and_active_entities_are_added(self):
        result = self.build(
            turns=[
                turn(
                    1,
                    last_observations=[{"id": "observation-1"}],
                    active_entities=[{"id": "entity-1"}],
                )
            ]
        )

        self.assertEqual(
            result["conversation_state"]["last_observations"],
            [{"id": "observation-1"}],
        )
        self.assertEqual(
            result["conversation_state"]["active_entities"],
            [{"id": "entity-1"}],
        )

    def test_capability_descriptions_are_added_in_declared_order(self):
        capabilities = [
            {"provider_id": "travel", "description": "旅行を振り返る"},
            {"provider_id": "photo", "description": "写真を探す"},
        ]

        result = self.build(capabilities=capabilities)

        self.assertEqual(result["capability_context"], capabilities)

    def test_redaction_is_recursive_and_does_not_mutate_input(self):
        original = turn(
            1,
            active_entities=[{"id": "entity-1", "token": "sensitive"}],
        )

        result = self.build(turns=[original])

        self.assertEqual(
            result["conversation_state"]["active_entities"][0]["token"],
            "[REDACTED]",
        )
        self.assertEqual(original.active_entities[0]["token"], "sensitive")

    def test_visibility_filter_uses_only_explicit_visibility(self):
        result = self.build(
            turns=[
                turn(
                    1,
                    last_observations=[
                        {"id": "public", "visibility": "public"},
                        {"id": "private", "visibility": "private"},
                        {"id": "unspecified"},
                    ],
                    active_entities=[
                        {"id": "family", "visibility": "family"},
                        {"id": "private", "visibility": "private"},
                    ],
                )
            ]
        )

        self.assertEqual(
            [
                item["id"]
                for item in result["conversation_state"]["last_observations"]
            ],
            ["public", "unspecified"],
        )
        self.assertEqual(
            [item["id"] for item in result["conversation_state"]["active_entities"]],
            ["family"],
        )

    def test_guest_visibility_excludes_family_entity(self):
        result = self.build(
            turns=[
                turn(1, active_entities=[{"id": "trip-1", "visibility": "family"}])
            ],
            allowed=frozenset({"public", "shared", "unknown"}),
        )

        self.assertEqual(result["conversation_state"]["active_entities"], [])

    def test_family_visibility_allows_family_entity(self):
        entity = {"id": "trip-1", "visibility": "family"}
        result = self.build(
            turns=[turn(1, active_entities=[entity])],
            allowed=frozenset({"public", "shared", "family", "unknown"}),
        )

        self.assertEqual(result["conversation_state"]["active_entities"], [entity])

    def test_byte_limit_drops_items_without_summarizing_them(self):
        unlimited = self.build(turns=[turn(1), turn(2)])
        one_turn_size = len(
            json.dumps(
                self.build(turns=[turn(2)]),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        builder = ConversationContextBuilder(
            ContextAssemblyConfig(max_bytes=one_turn_size)
        )

        result = self.build(builder, [turn(1), turn(2)])

        encoded = json.dumps(
            result, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        self.assertLessEqual(len(encoded), one_turn_size)
        self.assertEqual(
            result["conversation_context"], unlimited["conversation_context"][-1:]
        )

    def test_natural_language_is_opaque_and_does_not_trigger_decisions(self):
        opaque = turn(
            1,
            active_entities=[
                {"value": "旅行の話だから昨日の話題を継続", "visibility": "public"}
            ],
        )

        result = self.build(turns=[opaque])

        self.assertEqual(
            result["conversation_state"]["active_entities"][0]["value"],
            "旅行の話だから昨日の話題を継続",
        )
        self.assertNotIn("provider_id", result["conversation_state"])
        self.assertNotIn("operation_id", result["conversation_state"])


if __name__ == "__main__":
    unittest.main()
