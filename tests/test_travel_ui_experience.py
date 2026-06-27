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

    def test_experience_photos_have_more_button_and_page_loader(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function loadExperiencePhotosPage(elements, data, offset, limit)", source)
        self.assertIn("function appendExperiencePhotos(data, pageData)", source)
        self.assertIn("function renderExperiencePhotoControls(elements, data)", source)
        self.assertIn('moreButton.textContent = "もっと見る"', source)
        self.assertIn('"/photos?limit="', source)
        self.assertIn('"&offset="', source)
        self.assertIn("data.experiencePhotosNextOffset || 0", source)

    def test_experience_photo_cards_do_not_render_persistent_action_buttons(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function linkExperiencePhoto(elements, data, assetId, linkType)", source)
        self.assertNotIn('textContent = "採用"', source)
        self.assertNotIn('textContent = "リンク済みにする"', source)
        self.assertNotIn('textContent = "カバーにする"', source)
        self.assertNotIn('textContent = "候補から外す"', source)
        self.assertIn('"/photo-links"', source)
        self.assertIn('photo_asset_id: assetId', source)
        self.assertIn('link_type: linkType || "linked"', source)

    def test_experience_detail_renders_simple_photo_section(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn('title.textContent = "写真"', source)
        self.assertIn('badge.textContent = "カバー"', source)
        self.assertNotIn('badge.textContent = "リンク済み"', source)
        self.assertNotIn('badge.textContent = "候補"', source)
        self.assertNotIn("function renderExperienceLinkedPhotosSection", source)
        self.assertIn("function isExperiencePhotoAlreadyLinked(data, photo)", source)
        self.assertNotIn("linkedPhotosSection = renderExperienceLinkedPhotosSection(elements, data)", source)

    def test_experience_photo_section_has_explicit_action_entrypoints(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function renderExperiencePhotoHeaderActions(elements, data)", source)
        self.assertIn('coverButton.textContent = "代表画像を選択"', source)
        self.assertIn('outOfRangeButton.textContent = "期間外写真を追加"', source)
        self.assertIn("function showOutOfRangePhotoSearch(elements, data)", source)

    def test_experience_cover_selection_mode_functions_exist(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("var experienceCoverSelectionMode = false;", source)
        self.assertIn("function startExperienceCoverSelectionMode(elements, data)", source)
        self.assertIn("function cancelExperienceCoverSelectionMode(elements, data)", source)
        self.assertIn("function selectExperienceCoverPhoto(elements, data, assetId)", source)
        self.assertIn('linkExperiencePhoto(elements, data, assetId, "cover");', source)
        self.assertIn('selectButton.textContent = "代表にする"', source)

    def test_experience_photo_linking_updates_current_detail_state(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function mergeExperiencePhotoLink(data, link)", source)
        self.assertIn("function markExperiencePhotoLinkArchived(data, link)", source)
        self.assertIn("mergeExperiencePhotoLink(data, response.link);", source)
        self.assertIn("markExperiencePhotoLinkArchived(data, response.link);", source)
        self.assertIn("renderExperienceDetail(elements, data);", source)
        self.assertIn("function appendVisiblePhotoLinksToExperience(data)", source)
        self.assertIn("appendVisiblePhotoLinksToExperience(data);", source)
        self.assertNotIn("await loadExperienceDetail(experienceId);\n    setTravelStatus(elements, \"写真リンク保存済み\"", source)

    def test_experience_photo_candidates_are_hidden_through_persistent_link_api(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function hideExperiencePhotoCandidate(elements, data, assetId)", source)
        self.assertIn('linkExperiencePhoto(elements, data, assetId, "hidden");', source)
        self.assertIn('linkType === "hidden" || linkType === "excluded"', source)
        self.assertIn("function isExperiencePhotoCandidateHidden(data, photo)", source)
        self.assertIn('links[index].link_type === "hidden" || links[index].link_type === "excluded"', source)
        self.assertNotIn("hiddenExperiencePhotoCandidates", source)

    def test_experience_photo_cover_can_be_archived_from_ui(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function archiveExperiencePhotoLink(elements, data, linkId, successMessage)", source)
        self.assertIn('encodeURIComponent(linkId) +', source)

    def test_out_of_range_photo_search_form_and_add_function_exist(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function renderOutOfRangePhotoSearchForm(elements, data)", source)
        self.assertIn('fromInput.type = "datetime-local"', source)
        self.assertIn('toInput.type = "datetime-local"', source)
        self.assertIn('searchButton.textContent = "検索"', source)
        self.assertIn('cancelButton.textContent = "キャンセル"', source)
        self.assertIn("function loadOutOfRangePhotoSearch(", source)
        self.assertIn('"/photo-search?from="', source)
        self.assertIn("function addOutOfRangeExperiencePhoto(elements, data, assetId)", source)
        self.assertIn('linkExperiencePhoto(elements, data, assetId, "linked")', source)
        self.assertIn('addButton.textContent = isExperiencePhotoAlreadyLinked', source)

    def test_out_of_range_datetime_conversion_avoids_date_parsing(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertIn("function datetimeLocalToIso(value)", source)
        self.assertIn('":00+09:00"', source)
        self.assertNotIn("Date.parse", source)
        self.assertNotIn("new Date(", source)

    def test_travel_js_avoids_safari_unfriendly_syntax(self) -> None:
        source = TRAVEL_JS.read_text(encoding="utf-8")

        self.assertNotIn(".flatMap(", source)
        self.assertNotIn("=>", source)
        self.assertNotIn("?.", source)
        self.assertNotIn("??", source)
        self.assertNotIn(".replaceAll(", source)


if __name__ == "__main__":
    unittest.main()
