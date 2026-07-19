import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text()
JS = (ROOT / "frontend/static/chat-trace.js").read_text()
APP = (ROOT / "frontend/static/app.js").read_text()


class ChatTraceUiTest(unittest.TestCase):
    def test_developer_tab_controls_and_mobile_structure_exist(self) -> None:
        self.assertIn('data-tab="chat-trace-panel"', HTML)
        for label in ("相談用コピー", "完全トレースコピー", "JSONコピー", "全トレース消去"):
            self.assertIn(label, HTML)
        self.assertIn("chat-trace-layout", HTML)

    def test_lazy_fetch_detail_copy_fallback_and_clear_confirm(self) -> None:
        self.assertIn('api("/api/developer/chat-traces?limit=50")', JS)
        self.assertIn("/api/developer/chat-traces/${encodeURIComponent(turnId)}", JS)
        self.assertIn("navigator.clipboard.writeText", JS)
        self.assertIn('document.execCommand("copy")', JS)
        self.assertIn("confirm(", JS)
        self.assertIn("textContent", JS)
        self.assertIn("reasoning", JS)
        self.assertIn("anomaly_flags", JS)

    def test_general_screen_does_not_initialize_developer_trace(self) -> None:
        self.assertIn("initChatTrace();", APP)
        self.assertNotIn("refreshChatTraces", APP)
        self.assertIn("developerInitialized", APP)


if __name__ == "__main__":
    unittest.main()
