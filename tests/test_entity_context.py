import inspect
import unittest
from datetime import datetime, timezone

from backend.entity_context import EntityContextBuilder, EntityContextConfig
from backend.observation import ObservationEnvelopeBuilder


class EntityContextBuilderTest(unittest.TestCase):
    def observation(self, candidates):
        return ObservationEnvelopeBuilder(
            clock=lambda: datetime(2026, 7, 6, tzinfo=timezone.utc)
        ).build(
            provider_id="travel",
            operation_id="get_trips",
            raw_result={"success": True, "result": {}},
            details={
                "visibility": "family",
                "entity_candidates": candidates,
            },
        )

    def test_projects_valid_candidates_with_provenance(self):
        observation = self.observation(
            [
                {"entity_type": "trip", "id": "trip-1", "label": "福岡旅行"},
                {"entity_type": "trip", "label": "IDなし"},
            ]
        )

        result = EntityContextBuilder().build([observation])

        self.assertEqual(
            result,
            [
                {
                    "entity_type": "trip",
                    "id": "trip-1",
                    "label": "福岡旅行",
                    "source_provider": "travel",
                    "source_operation": "get_trips",
                    "observed_at": "2026-07-06T00:00:00+00:00",
                    "visibility": "family",
                }
            ],
        )

    def test_limit_preserves_provider_order_and_keeps_latest_items(self):
        observation = self.observation(
            [
                {"entity_type": "trip", "id": f"trip-{index}", "label": str(index)}
                for index in range(3)
            ]
        )

        result = EntityContextBuilder(EntityContextConfig(max_entities=2)).build(
            [observation], [{"opaque": "previous"}]
        )

        self.assertEqual([entity["id"] for entity in result], ["trip-1", "trip-2"])

    def test_candidate_labels_are_opaque_and_do_not_trigger_resolution(self):
        observation = self.observation(
            [
                {
                    "entity_type": "trip",
                    "id": "trip-1",
                    "label": "福岡旅行ならこのtrip_id",
                }
            ]
        )

        result = EntityContextBuilder().build([observation])

        self.assertEqual(result[0]["id"], "trip-1")
        self.assertEqual(result[0]["label"], "福岡旅行ならこのtrip_id")
        source = inspect.getsource(EntityContextBuilder)
        self.assertNotIn("user_text", source)
        self.assertNotIn("keyword", source)
        self.assertNotIn("ranking", source)
        self.assertNotIn("resolve", source.casefold())


if __name__ == "__main__":
    unittest.main()
