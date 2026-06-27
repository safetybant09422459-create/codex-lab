import unittest

from backend.search_engine import (
    SearchDocument,
    SearchEngine,
    SearchKeyword,
    SearchTerm,
    normalize_search_text,
)


class SearchEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SearchEngine()

    def test_search_returns_entity_candidates_without_skill_knowledge(self) -> None:
        documents = [
            SearchDocument(
                id="photo-2",
                label="Beach Sunset",
                document="beach sunset okinawa",
                metadata={
                    "skill_id": "photo",
                    "entity_type": "asset",
                    "source": "photo_repository",
                },
                keywords=(
                    SearchKeyword(
                        value="Beach Sunset",
                        matched_by="caption",
                        exact_score=1.0,
                        partial_score=0.8,
                    ),
                ),
            ),
            SearchDocument(
                id="photo-1",
                label="Beach Morning",
                document="beach morning",
                metadata={
                    "skill_id": "photo",
                    "entity_type": "asset",
                    "source": "photo_repository",
                },
                keywords=(
                    SearchKeyword(
                        value="Beach Morning",
                        matched_by="caption",
                        exact_score=1.0,
                        partial_score=0.8,
                    ),
                ),
            ),
        ]

        candidates = self.engine.search("beach", documents)

        self.assertEqual(
            [candidate.entity.entity_id for candidate in candidates],
            ["photo-1", "photo-2"],
        )
        self.assertTrue(all(candidate.entity.skill_id == "photo" for candidate in candidates))
        self.assertTrue(all(candidate.matched_by == "caption" for candidate in candidates))

    def test_search_accepts_weighted_terms_from_an_external_provider(self) -> None:
        document = SearchDocument(
            id="garden-1",
            label="Rose bed",
            document="rose bed",
            metadata={
                "skill_id": "garden",
                "entity_type": "planting",
                "source": "garden_repository",
            },
            keywords=(
                SearchKeyword(
                    value="rose",
                    matched_by="name",
                    exact_score=1.0,
                    partial_score=0.8,
                ),
            ),
        )

        candidates = self.engine.search(
            (SearchTerm(value="flower", score_scale=0.5, matched_by_prefix="alias:"),
             SearchTerm(value="rose", score_scale=0.5, matched_by_prefix="alias:")),
            [document],
        )

        self.assertEqual(candidates[0].score, 0.5)
        self.assertEqual(candidates[0].matched_by, "alias:name")

    def test_document_is_a_generic_fallback_search_target(self) -> None:
        document = SearchDocument(
            id="memory-1",
            label="School day",
            document="first day at school",
            metadata={
                "skill_id": "memory",
                "entity_type": "memory",
                "source": "memory_repository",
            },
            keywords=(),
        )

        candidates = self.engine.search("school", [document])

        self.assertEqual(candidates[0].score, 0.3)
        self.assertEqual(candidates[0].matched_by, "document")

    def test_document_without_common_entity_metadata_is_ignored(self) -> None:
        document = SearchDocument(
            id="item-1",
            label="Item",
            document="item",
            metadata={"skill_specific": True},
            keywords=(),
        )

        self.assertEqual(self.engine.search("item", [document]), [])

    def test_normalization_is_skill_neutral(self) -> None:
        self.assertEqual(normalize_search_text(" Ｆｏｏ Bar！ "), "foobar")


if __name__ == "__main__":
    unittest.main()
