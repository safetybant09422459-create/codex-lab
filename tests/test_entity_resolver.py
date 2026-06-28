import unittest

from pydantic import ValidationError

from backend.chat_core import (
    EntityCandidate,
    EntityRef,
    EntityResolutionRequest,
    EntityResolutionResult,
)
from backend.travel_entity_resolver import TravelEntityResolver


class EntityResolutionContractTest(unittest.TestCase):
    def test_request_and_result_validate_and_serialize(self) -> None:
        request = EntityResolutionRequest(
            query="福岡旅行",
            skill_id="travel",
            entity_types=("trip",),
            context={"selected_entity_id": "trip-fukuoka"},
            limit=5,
        )
        entity = EntityRef(
            skill_id="travel",
            entity_type="trip",
            entity_id="trip-fukuoka",
            label="福岡旅行",
            source="test",
        )
        result = EntityResolutionResult(
            status="resolved",
            candidates=[EntityCandidate(entity=entity, score=1.0, matched_by="title")],
            resolved_entity=entity,
        )

        self.assertEqual(request.model_dump()["entity_types"], ("trip",))
        self.assertEqual(result.model_dump()["status"], "resolved")
        self.assertEqual(result.resolved_entity, entity)

    def test_request_requires_positive_limit(self) -> None:
        with self.assertRaises(ValidationError):
            EntityResolutionRequest(query="旅行", limit=0)


class TravelEntityResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = TravelEntityResolver()
        self.request = EntityResolutionRequest(
            query="兵庫",
            skill_id="travel",
            entity_types=("trip",),
        )

    def test_zero_candidates_is_not_found(self) -> None:
        result = self.resolver.resolve(self.request, trips=[])

        self.assertEqual(result.status, "not_found")
        self.assertEqual(result.candidates, [])
        self.assertIsNone(result.resolved_entity)

    def test_one_candidate_is_resolved(self) -> None:
        trip = {"id": "trip-suma", "title": "須磨", "prefectures": "兵庫県"}

        result = self.resolver.resolve(self.request, trips=[trip])

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved_entity.entity_id, "trip-suma")
        self.assertEqual(result.diagnostics["candidate_count"], 1)

    def test_multiple_candidates_is_ambiguous(self) -> None:
        trips = [
            {"id": "trip-suma", "title": "須磨", "prefectures": "兵庫県"},
            {"id": "trip-awaji", "title": "淡路", "prefectures": "兵庫県"},
        ]

        result = self.resolver.resolve(self.request, trips=trips)

        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(len(result.candidates), 2)
        self.assertIsNone(result.resolved_entity)

    def test_runtime_get_trips_result_is_accepted(self) -> None:
        trip = {"id": "trip-suma", "title": "須磨", "prefectures": "兵庫県"}

        result = self.resolver.resolve(
            self.request, runtime_result={"trips": [trip]}
        )

        self.assertEqual(result.status, "resolved")


if __name__ == "__main__":
    unittest.main()
