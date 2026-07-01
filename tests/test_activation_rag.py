import unittest
from datetime import datetime, timezone

from backend.activation_rag import ActivationRag
from backend.rag_core import RagDocument
from backend.rag_store import InMemoryRagStore
from backend.travel_rag_provider import TravelRagDocumentBuilder


UPDATED_AT = datetime(2026, 6, 20, tzinfo=timezone.utc)


class StaticProvider:
    def __init__(self, documents):
        self._documents = documents

    def documents(self):
        return list(self._documents)


def document(
    document_id: str,
    *,
    source_skill: str,
    entity_type: str,
    entity_id: str,
    text: str,
    visibility: str = "private",
):
    return RagDocument(
        id=document_id,
        source_skill=source_skill,
        entity_type=entity_type,
        entity_id=entity_id,
        text=text,
        metadata={"canonical_source": f"{source_skill}_repository"},
        visibility=visibility,
        updated_at=UPDATED_AT,
    )


class TravelRagDocumentBuilderTest(unittest.TestCase):
    def setUp(self):
        self.trip = {
            "id": "trip-fukuoka",
            "title": "福岡旅行",
            "start_date": "2026-04-02",
            "end_date": "2026-04-04",
            "prefectures": "福岡県",
            "privacy_level": "family",
            "outing_type": "overnight",
            "memo": "家族旅行",
            "status": "active",
            "updated_at": "2026-06-20T12:00:00+09:00",
        }
        self.item = {
            "id": "item-marine-world",
            "trip_id": "trip-fukuoka",
            "item_type": "spot",
            "display_title": "マリンワールド海の中道",
            "place_name": "マリンワールド海の中道",
            "category": "観光",
            "memo": "福岡旅行最終日の水族館",
            "start_at": "2026-04-04T10:00:00+09:00",
            "status": "planned",
            "updated_at": "2026-06-20T12:30:00+09:00",
        }
        self.builder = TravelRagDocumentBuilder()

    def test_trip_and_experience_become_common_documents(self):
        documents = self.builder.build_many(
            [self.trip], {"trip-fukuoka": [self.item]}
        )

        self.assertEqual(len(documents), 2)
        trip, experience = documents
        self.assertEqual(
            (trip.source_skill, trip.entity_type, trip.entity_id),
            ("travel", "trip", "trip-fukuoka"),
        )
        self.assertIn("福岡旅行", trip.text)
        self.assertIn("マリンワールド海の中道", trip.text)
        self.assertEqual(
            (experience.source_skill, experience.entity_type, experience.entity_id),
            ("travel", "experience", "item-marine-world"),
        )
        self.assertIn("3日目", experience.text)

    def test_travel_fields_stay_in_metadata_and_visibility_is_preserved(self):
        experience = self.builder.build_experience(self.trip, self.item)

        self.assertIsNotNone(experience)
        assert experience is not None
        self.assertEqual(experience.visibility, "family")
        self.assertEqual(experience.metadata["trip_id"], "trip-fukuoka")
        self.assertEqual(experience.metadata["item_type"], "spot")
        self.assertFalse(hasattr(experience, "trip_id"))
        self.assertFalse(hasattr(experience, "place_name"))


class RagStoreTest(unittest.TestCase):
    def setUp(self):
        builder = TravelRagDocumentBuilder()
        trips = [
            {
                "id": "trip-fukuoka",
                "title": "福岡旅行",
                "prefectures": "福岡県",
                "privacy_level": "private",
                "updated_at": "2026-06-20T12:00:00+09:00",
            },
            {
                "id": "trip-german-forest",
                "title": "APM＆ドイツの森",
                "prefectures": "岡山県",
                "privacy_level": "family",
                "updated_at": "2026-06-20T12:00:00+09:00",
            },
            {
                "id": "trip-kobe",
                "title": "まい初旅行",
                "prefectures": "兵庫県",
                "privacy_level": "family",
                "updated_at": "2026-06-20T12:00:00+09:00",
            },
        ]
        timelines = {
            "trip-fukuoka": [
                {
                    "id": "marine-world",
                    "trip_id": "trip-fukuoka",
                    "item_type": "spot",
                    "display_title": "マリンワールド海の中道",
                    "memo": "水族館",
                    "updated_at": "2026-06-20T12:00:00+09:00",
                }
            ],
            "trip-german-forest": [
                {
                    "id": "forest-train",
                    "trip_id": "trip-german-forest",
                    "item_type": "spot",
                    "display_title": "ブランコと汽車",
                    "updated_at": "2026-06-20T12:00:00+09:00",
                }
            ],
            "trip-kobe": [
                {
                    "id": "kobe-apm",
                    "trip_id": "trip-kobe",
                    "item_type": "spot",
                    "display_title": "アンパンマンミュージアム",
                    "updated_at": "2026-06-20T12:00:00+09:00",
                }
            ],
        }
        self.documents = builder.build_many(trips, timelines)
        self.documents.append(
            document(
                "calendar:1",
                source_skill="calendar",
                entity_type="calendar_event",
                entity_id="event-1",
                text="福岡 出張予定",
                visibility="shared",
            )
        )
        self.store = InMemoryRagStore(self.documents)

    def test_fukuoka_aquarium_ranks_marine_world_documents(self):
        results = self.store.search("福岡 水族館")

        self.assertIn("marine-world", [result.document.entity_id for result in results[:2]])
        self.assertTrue(all(result.score <= 1.0 for result in results))

    def test_german_forest_returns_trip_and_related_experience(self):
        results = self.store.search("ドイツの森")
        ids = [result.document.entity_id for result in results]

        self.assertIn("trip-german-forest", ids)
        self.assertIn("forest-train", ids)

    def test_kobe_anpanman_returns_relevant_experience_or_trip(self):
        results = self.store.search("神戸 アンパンマン")

        self.assertIn("kobe-apm", [result.document.entity_id for result in results[:2]])

    def test_source_skill_and_entity_type_filters(self):
        travel = self.store.search("福岡", source_skill="travel")
        experiences = self.store.search("福岡", entity_type="experience")

        self.assertTrue(travel)
        self.assertTrue(all(r.document.source_skill == "travel" for r in travel))
        self.assertTrue(experiences)
        self.assertTrue(all(r.document.entity_type == "experience" for r in experiences))

    def test_visibility_filter_excludes_private_documents(self):
        results = self.store.search(
            "福岡", allowed_visibilities={"family", "shared", "public"}
        )

        self.assertTrue(results)
        self.assertTrue(all(r.document.visibility != "private" for r in results))

    def test_activation_search_only_returns_candidates(self):
        rag = ActivationRag([StaticProvider(self.documents)])

        results = rag.search("福岡 水族館")

        self.assertTrue(results)
        self.assertFalse(hasattr(results[0], "tool_id"))
        self.assertEqual(
            results[0].document.metadata["canonical_source"],
            "travel_repository",
        )

    def test_activation_filters_weak_unrelated_matches(self):
        rag = ActivationRag([StaticProvider(self.documents)])

        for query in ("おはよう", "今日の天気は？", "量子力学について教えて"):
            with self.subTest(query=query):
                self.assertEqual(rag.search(query), [])

    def test_activation_limits_experiences_per_trip_and_keeps_trip(self):
        builder = TravelRagDocumentBuilder()
        trip = {
            "id": "trip-fukuoka",
            "title": "福岡旅行",
            "privacy_level": "family",
            "updated_at": "2026-06-20T12:00:00+09:00",
        }
        timeline = [
            {
                "id": f"item-{index}",
                "trip_id": "trip-fukuoka",
                "item_type": "spot",
                "display_title": f"福岡旅行の体験{index}",
            }
            for index in range(8)
        ]
        rag = ActivationRag(
            [StaticProvider(builder.build_many([trip], {"trip-fukuoka": timeline}))]
        )

        results = rag.search("福岡旅行", limit=5)

        self.assertIn("trip-fukuoka", [result.document.entity_id for result in results])
        self.assertLessEqual(
            sum(result.document.entity_type == "experience" for result in results),
            2,
        )


if __name__ == "__main__":
    unittest.main()
