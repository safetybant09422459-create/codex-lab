import unittest

from backend.travel_search_expansion import TravelSearchExpansionProvider


class TravelSearchExpansionProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = TravelSearchExpansionProvider()

    def test_normalize_handles_width_case_and_travel_request_suffix(self) -> None:
        self.assertEqual(self.provider.normalize(" ＡＰＭ を開いて。 "), "apm")

    def test_expand_owns_travel_vocabulary(self) -> None:
        self.assertEqual(self.provider.expand("神戸旅行"), ("兵庫", "須磨"))
        self.assertEqual(
            self.provider.expand("APM"),
            ("アンパンマン", "アンパンマンミュージアム"),
        )

    def test_terms_separate_direct_and_auxiliary_queries(self) -> None:
        terms = self.provider.terms("神戸旅行を見せて")

        self.assertEqual([term.value for term in terms[:2]], ["神戸旅行", "神戸"])
        self.assertEqual([term.value for term in terms[2:]], ["兵庫", "須磨"])
        self.assertTrue(all(term.score_scale == 1.0 for term in terms[:2]))
        self.assertTrue(all(term.score_scale < 1.0 for term in terms[2:]))
        self.assertTrue(
            all(term.matched_by_prefix == "query_expansion:" for term in terms[2:])
        )

    def test_empty_query_has_no_terms(self) -> None:
        self.assertEqual(self.provider.terms("  。 "), ())


if __name__ == "__main__":
    unittest.main()
