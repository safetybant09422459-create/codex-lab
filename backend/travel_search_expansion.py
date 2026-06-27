from __future__ import annotations

from .search_engine import SearchTerm, normalize_search_text


_QUERY_EXPANSIONS = {
    "神戸": ("兵庫", "須磨"),
    "須磨": ("須磨シーワールド",),
    "シーワールド": ("須磨シーワールド", "水族館"),
    "apm": ("アンパンマン", "アンパンマンミュージアム"),
    "アンパンマン": ("apm", "アンパンマンミュージアム"),
}

_REQUEST_SUFFIXES = (
    "を開いてください", "開いてください", "を表示してください", "表示してください",
    "を見せてください", "見せてください", "を開いて", "開いて", "を表示して",
    "表示して", "を見せて", "見せて", "を開く", "開く",
)


class TravelSearchExpansionProvider:
    """Own Travel vocabulary and convert a user query into generic terms."""

    def normalize(self, query: str) -> str:
        if not isinstance(query, str):
            return ""
        compact = normalize_search_text(query)
        for suffix in _REQUEST_SUFFIXES:
            normalized_suffix = normalize_search_text(suffix)
            if compact.endswith(normalized_suffix):
                compact = compact[: -len(normalized_suffix)]
                break
        return compact.strip("「」『』\"'")

    def expand(self, query: str) -> tuple[str, ...]:
        normalized = self.normalize(query)
        expansions: list[str] = []
        for key, values in _QUERY_EXPANSIONS.items():
            if self.normalize(key) not in normalized:
                continue
            for value in values:
                term = self.normalize(value)
                if term and term not in expansions:
                    expansions.append(term)
        return tuple(expansions)

    def terms(self, query: str) -> tuple[SearchTerm, ...]:
        normalized = self.normalize(query)
        if not normalized:
            return ()
        direct_terms = [normalized]
        reduced = normalized
        if reduced.endswith("の旅行"):
            reduced = reduced[: -len("の旅行")]
        elif reduced.endswith("旅行") and reduced != "旅行":
            reduced = reduced[: -len("旅行")]
        if reduced and reduced not in direct_terms:
            direct_terms.append(reduced)

        terms = [SearchTerm(value=value) for value in direct_terms]
        terms.extend(
            SearchTerm(
                value=value,
                score_scale=0.55,
                matched_by_prefix="query_expansion:",
            )
            for value in self.expand(normalized)
            if value not in direct_terms
        )
        return tuple(terms)


_DEFAULT_PROVIDER = TravelSearchExpansionProvider()


def normalize_travel_query(query: str) -> str:
    return _DEFAULT_PROVIDER.normalize(query)


def expand_travel_query(query: str) -> tuple[str, ...]:
    return _DEFAULT_PROVIDER.expand(query)
