import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRAVEL_JS = ROOT_DIR / "frontend" / "static" / "travel.js"


class TravelUiExperienceTest(unittest.TestCase):
    def test_timeline_click_loads_experience_detail(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn('button.setAttribute("data-experience-id"', source)
        self.assertIn("loadExperienceDetail(experienceId);", source)
        self.assertNotIn("loadSpotDetail(spotId);", source)

    def test_experience_detail_uses_experience_api_and_keeps_spot_aliases(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function renderExperienceDetail(elements, data)", source)
        self.assertIn("function loadExperienceDetail(experienceId)", source)
        self.assertIn('"/api/travel/experiences/"', source)
        self.assertIn("function renderSpotDetail(elements, data)", source)
        self.assertIn("function loadSpotDetail(spotId)", source)

    def test_experience_type_is_rendered_in_detail(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function experienceTypeLabel(experience)", source)
        self.assertIn('"Experience Type: " + experienceTypeLabel(experience)', source)


if __name__ == "__main__":
    unittest.main()
