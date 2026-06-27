import unittest

from backend.travel_search_index import TravelSearchIndex


class TravelSearchIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.index = TravelSearchIndex()
        self.trips = [
            {
                "id": "trip-suma",
                "title": "須磨シーワールド",
                "prefectures": '["兵庫県"]',
                "memo": "神戸でオルカショーと水族館を楽しむ",
                "start_date": "2026-05-08",
                "end_date": "2026-05-09",
                "outing_type": "overnight",
            },
            {
                "id": "trip-fukuoka",
                "title": "福岡旅行",
                "prefectures": "福岡県",
                "memo": "屋台めぐり",
                "start_date": "2025-11-01",
                "end_date": "2025-11-03",
                "outing_type": "旅行",
            },
        ]

    def test_title_exact_match_has_highest_score(self) -> None:
        candidates = self.index.search("福岡旅行", self.trips)

        self.assertEqual(candidates[0].entity.entity_id, "trip-fukuoka")
        self.assertEqual(candidates[0].score, 1.0)
        self.assertIn("title_exact", candidates[0].matched_by)

    def test_title_partial_match(self) -> None:
        candidates = self.index.search("シーワールド", self.trips)

        self.assertEqual(candidates[0].entity.entity_id, "trip-suma")
        self.assertIn("title_partial", candidates[0].matched_by)

    def test_prefectures_match(self) -> None:
        candidates = self.index.search("兵庫の旅行見せて", self.trips)

        self.assertEqual([item.entity.entity_id for item in candidates], ["trip-suma"])
        self.assertIn("prefectures", candidates[0].matched_by)

    def test_memo_match(self) -> None:
        candidates = self.index.search("オルカ", self.trips)

        self.assertEqual([item.entity.entity_id for item in candidates], ["trip-suma"])
        self.assertIn("memo", candidates[0].matched_by)

    def test_query_expansion_is_auxiliary(self) -> None:
        trip = dict(self.trips[0], memo="")
        candidates = self.index.search("神戸旅行", [trip])

        self.assertEqual(candidates[0].entity.entity_id, "trip-suma")
        self.assertIn("query_expansion", candidates[0].matched_by)
        self.assertLess(candidates[0].score, 0.86)

    def test_date_match_and_scores_are_bounded(self) -> None:
        candidates = self.index.search("2026", self.trips)

        self.assertEqual([item.entity.entity_id for item in candidates], ["trip-suma"])
        self.assertIn("date", candidates[0].matched_by)
        self.assertTrue(all(0.0 <= item.score <= 1.0 for item in candidates))

    def test_multiple_candidate_order_is_deterministic(self) -> None:
        trips = [
            {"id": "trip-z", "title": "淡路旅行", "prefectures": "兵庫県"},
            {"id": "trip-a", "title": "神戸旅行", "prefectures": "兵庫県"},
        ]

        forward = self.index.search("兵庫", trips)
        reverse = self.index.search("兵庫", reversed(trips))

        self.assertEqual(
            [item.entity.entity_id for item in forward],
            [item.entity.entity_id for item in reverse],
        )
        self.assertEqual(
            [item.entity.entity_id for item in forward],
            ["trip-z", "trip-a"],
        )

if __name__ == "__main__":
    unittest.main()
