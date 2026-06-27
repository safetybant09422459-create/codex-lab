import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = (ROOT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")
CHAT_JS = (ROOT_DIR / "frontend" / "static" / "chat.js").read_text(encoding="utf-8")


class ChatUiTest(unittest.TestCase):
    def test_home_contains_chat_controls_and_script(self) -> None:
        self.assertIn('id="chat-history"', INDEX_HTML)
        self.assertIn('id="chat-input"', INDEX_HTML)
        self.assertIn('id="chat-submit"', INDEX_HTML)
        self.assertIn('src="/static/chat.js"', INDEX_HTML)

    def test_chat_uses_server_chat_api_only(self) -> None:
        self.assertIn('api("/api/chat"', CHAT_JS)
        self.assertIn("context: currentContext", CHAT_JS)
        self.assertIn('hasOwnProperty.call(data, "updated_context")', CHAT_JS)
        self.assertNotIn("api.openai.com", CHAT_JS)
        self.assertNotIn("/api/runtime", CHAT_JS)

    def test_chat_renders_trip_fields_and_travel_link(self) -> None:
        for field in ("title", "start_date", "end_date", "prefectures", "memo"):
            self.assertIn("trip." + field, CHAT_JS)
        self.assertIn('link.href = "#travel"', CHAT_JS)

    def test_chat_renders_server_navigation_and_named_trip_candidates(self) -> None:
        self.assertIn("appendNavigation(elements.history, data.navigation)", CHAT_JS)
        self.assertIn("link.href = navigation.target", CHAT_JS)
        self.assertIn("link.dataset.tripId = navigation.trip_id", CHAT_JS)
        self.assertIn("Array.isArray(data.candidates)", CHAT_JS)
        self.assertIn("[data.result.trip]", CHAT_JS)

    def test_trip_list_link_remains_plain_travel_navigation(self) -> None:
        self.assertIn('link.href = "#travel"', CHAT_JS)

    def test_chat_guards_ime_and_has_generic_error(self) -> None:
        self.assertIn("event.isComposing", CHAT_JS)
        self.assertIn("うまく取得できませんでした", CHAT_JS)


if __name__ == "__main__":
    unittest.main()
