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
        self.assertIn('aria-busy="false"', INDEX_HTML)
        self.assertIn('row.setAttribute("role", "alert")', CHAT_JS)
        self.assertIn('elements.history.setAttribute("aria-busy"', CHAT_JS)

    def test_chat_maps_transport_failures_and_only_retries_retryable_errors(self) -> None:
        api_js = (ROOT_DIR / "frontend" / "static" / "api.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("class ApiError extends Error", api_js)
        self.assertIn("this.retryable = retryable", api_js)
        self.assertIn('res.headers.get("X-Jarvis-Error-Code")', api_js)
        self.assertIn('code !== "chat_not_configured"', api_js)
        self.assertIn("error && error.retryable", CHAT_JS)
        self.assertIn("function chatErrorMessage(error)", CHAT_JS)
        self.assertIn("もう一度試す", CHAT_JS)
        self.assertIn("window.navigator.onLine", CHAT_JS)

    def test_chat_restores_bounded_tab_context_and_can_clear_server_state(self) -> None:
        self.assertIn('id="chat-clear"', INDEX_HTML)
        self.assertIn("window.sessionStorage", CHAT_JS)
        self.assertIn("window.crypto.getRandomValues", CHAT_JS)
        self.assertIn("history: conversationHistory.slice(-maxConversationTurns)", CHAT_JS)
        self.assertIn('api("/api/chat/session/reset"', CHAT_JS)
        self.assertIn("conversationHistory = []", CHAT_JS)
        self.assertIn("長期Memoryには自動保存されません", INDEX_HTML)

    def test_starters_describe_goals_instead_of_required_commands(self) -> None:
        self.assertIn("できることを知る", INDEX_HTML)
        self.assertIn("旅行を振り返る", INDEX_HTML)
        self.assertIn("最近の写真を知る", INDEX_HTML)
        self.assertNotIn("アンパンマンミュージアムの写真見せて", INDEX_HTML)

    def test_chat_has_no_photo_card_or_thumbnail_renderer(self) -> None:
        self.assertNotIn("chat-photo-card", CHAT_JS)
        self.assertNotIn("createPhotoCard", CHAT_JS)
        self.assertNotIn("thumbnail_url", CHAT_JS)


if __name__ == "__main__":
    unittest.main()
