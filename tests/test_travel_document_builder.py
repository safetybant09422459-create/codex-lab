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
            ["title", "prefectures", "memo", "date", "outing_type"],
        )

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
