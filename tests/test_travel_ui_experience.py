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

    def test_experience_edit_form_is_rendered_from_detail(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function renderExperienceEditForm(elements, data, errorText)", source)
        self.assertIn("function submitExperienceUpdate(event, elements, data)", source)
        self.assertIn("function cancelExperienceEdit(elements, data)", source)
        self.assertIn('editButton.textContent = "編集"', source)
        self.assertIn('titleInput.name = "display_title"', source)
        self.assertIn('memoInput.name = "memo"', source)
        self.assertIn('statusSelect.name = "status"', source)

    def test_experience_edit_uses_patch_api(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn('await api("/api/travel/experiences/" + encodeURIComponent(experienceId), {', source)
        self.assertIn('method: "PATCH"', source)
        self.assertIn("body: JSON.stringify(payload)", source)
        self.assertIn("await loadExperienceDetail(experienceId);", source)
        self.assertNotIn("/api/runtime/execute", source)

    def test_experience_edit_status_options_preserve_unknown_existing_status(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn('var experienceStatusOptions = ["planned", "completed", "skipped", "archived"];', source)
        self.assertIn("if (status && !experienceStatusIsKnown(status))", source)
        self.assertIn("appendExperienceStatusOption(statusSelect, status);", source)

    def test_experience_create_form_is_rendered_from_trip_detail(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn(
            "function renderExperienceCreateForm(elements, data, errorText)", source
        )
        self.assertIn("function submitExperienceCreate(event, elements, data)", source)
        self.assertIn("function cancelExperienceCreate(elements, data)", source)
        self.assertIn('createButton.textContent = "＋体験追加"', source)
        self.assertIn('typeSelect.name = "experience_type"', source)
        self.assertIn('titleInput.name = "display_title"', source)
        self.assertIn('memoInput.name = "memo"', source)
        self.assertIn('statusSelect.name = "status"', source)

    def test_experience_create_uses_trip_experience_post_api(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn(
            '"/api/travel/trips/" + encodeURIComponent(tripId) + "/experiences"',
            source,
        )
        self.assertIn('method: "POST"', source)
        self.assertIn("body: JSON.stringify(payload)", source)
        self.assertIn("await loadTravelDetail(tripId);", source)
        self.assertIn("await loadExperienceDetail(experienceId);", source)
        self.assertNotIn("/api/runtime/execute", source)

    def test_travel_js_avoids_safari_unfriendly_syntax(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertNotIn(".flatMap(", source)
        self.assertNotIn("=>", source)
        self.assertNotIn("?.", source)
        self.assertNotIn("??", source)
        self.assertNotIn(".replaceAll(", source)


if __name__ == "__main__":
    unittest.main()
