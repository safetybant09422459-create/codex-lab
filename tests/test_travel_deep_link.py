import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRAVEL_JS = (ROOT_DIR / "frontend" / "static" / "travel.js").read_text(
    encoding="utf-8"
)
SHELL_JS = (ROOT_DIR / "frontend" / "static" / "shell.js").read_text(
    encoding="utf-8"
)


class TravelDeepLinkTest(unittest.TestCase):
    def test_shell_resolves_screen_without_hash_query(self) -> None:
        self.assertIn('var queryIndex = hash.indexOf("?");', SHELL_JS)
        self.assertIn("hash = hash.slice(0, queryIndex);", SHELL_JS)

    def test_travel_reads_trip_id_from_hash(self) -> None:
        self.assertIn("function travelTripIdFromHash()", TRAVEL_JS)
        self.assertIn('hash.slice(0, queryIndex) !== "travel"', TRAVEL_JS)
        self.assertIn('params.get("trip_id") || ""', TRAVEL_JS)

    def test_deep_link_reuses_existing_trip_detail_loader(self) -> None:
        self.assertIn("loadTravelDetail(tripId, true);", TRAVEL_JS)
        self.assertIn(
            'api("/api/travel/trips/" + encodeURIComponent(tripId))',
            TRAVEL_JS,
        )

    def test_plain_travel_hash_keeps_list_view(self) -> None:
        self.assertIn("function handleTravelRoute()", TRAVEL_JS)
        self.assertIn("showList(elements);", TRAVEL_JS)
        self.assertIn("loadTravelTrips(false);", TRAVEL_JS)

    def test_back_from_direct_detail_loads_list_when_needed(self) -> None:
        self.assertIn(
            'if (loaded) {\n        setTravelStatus(nextElements, "取得済み", false);\n'
            "      } else {\n        loadTravelTrips(false);",
            TRAVEL_JS,
        )

    def test_invalid_trip_returns_to_list_with_light_error(self) -> None:
        self.assertIn(
            'setTravelStatus(elements, "旅行が見つかりませんでした。", true);',
            TRAVEL_JS,
        )
        self.assertIn("clearTravelDeepLink();", TRAVEL_JS)


if __name__ == "__main__":
    unittest.main()
