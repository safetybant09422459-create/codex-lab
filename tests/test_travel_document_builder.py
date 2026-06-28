import unittest
from datetime import datetime, timezone

from backend.travel_document_builder import TravelDocumentBuilder


class TravelDocumentBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = TravelDocumentBuilder()

    def test_build_converts_trip_to_search_document(self) -> None:
        verified_at = datetime(2026, 6, 27, tzinfo=timezone.utc)
        trip = {
            "id": "trip-suma",
            "title": "須磨シーワールド",
            "prefectures": ["兵庫県"],
            "memo": "オルカショー",
            "start_date": "2026-05-08",
            "end_date": "2026-05-09",
            "outing_type": "overnight",
        }

        document = self.builder.build(trip, verified_at=verified_at)

        self.assertIsNotNone(document)
        assert document is not None
        self.assertEqual(document.id, "trip-suma")
        self.assertEqual(document.label, "須磨シーワールド")
        self.assertIn("オルカショー", document.document)
        self.assertEqual(document.metadata["skill_id"], "travel")
        self.assertEqual(document.metadata["entity_type"], "trip")
        self.assertEqual(document.metadata["verified_at"], verified_at)
        self.assertEqual(document.metadata["trip"], trip)
        self.assertEqual(
            [keyword.matched_by for keyword in document.keywords],
            [
                "title",
                "prefectures",
                "location_terms",
                "regions",
                "memo",
                "date",
                "calendar",
                "season",
                "duration",
                "outing_type",
            ],
        )

    def test_build_derives_calendar_season_duration_and_region_facets(self) -> None:
        trip = {
            "id": "trip-osaka",
            "title": "大阪旅行",
            "prefectures": "大阪府",
            "start_date": "2026-05-13",
            "end_date": "2026-05-15",
            "outing_type": "overnight",
        }

        document = self.builder.build(trip)

        self.assertIsNotNone(document)
        assert document is not None
        self.assertIn("大阪府のおでかけ", document.document)
        self.assertIn("大阪の旅", document.document)
        self.assertIn("関西近畿", document.document)
        self.assertIn("2026年", document.document)
        self.assertIn("5月", document.document)
        self.assertIn("春", document.document)
        self.assertIn("2泊3日", document.document)

    def test_build_derives_day_trip_and_does_not_mutate_trip(self) -> None:
        trip = {
            "id": "trip-kagawa",
            "title": "香川日帰り",
            "prefectures": ["香川県"],
            "start_date": "2024-07-12",
            "end_date": "2024-07-12",
            "outing_type": "day_trip",
        }
        original = {**trip, "prefectures": list(trip["prefectures"])}

        document = self.builder.build(trip)

        self.assertIsNotNone(document)
        assert document is not None
        self.assertIn("四国", document.document)
        self.assertIn("夏", document.document)
        self.assertIn("日帰り", document.document)
        self.assertEqual(trip, original)

    def test_build_ignores_invalid_dates_when_deriving_facets(self) -> None:
        document = self.builder.build(
            {
                "id": "trip-invalid-date",
                "start_date": "not-a-date",
                "end_date": "also-not-a-date",
            }
        )

        self.assertIsNotNone(document)
        assert document is not None
        self.assertNotIn("calendar", [keyword.matched_by for keyword in document.keywords])

    def test_build_uses_outing_type_when_dates_are_missing(self) -> None:
        document = self.builder.build(
            {"id": "trip-no-dates", "outing_type": "day_trip"}
        )

        self.assertIsNotNone(document)
        assert document is not None
        self.assertIn("日帰り", document.document)

    def test_build_uses_id_as_label_and_omits_empty_keywords(self) -> None:
        document = self.builder.build({"id": "trip-untitled", "title": " "})

        self.assertIsNotNone(document)
        assert document is not None
        self.assertEqual(document.label, "trip-untitled")
        self.assertEqual(document.keywords, ())

    def test_build_rejects_non_trip_shapes(self) -> None:
        self.assertIsNone(self.builder.build(None))
        self.assertIsNone(self.builder.build({"title": "No id"}))
        self.assertIsNone(self.builder.build({"id": " "}))


if __name__ == "__main__":
    unittest.main()
