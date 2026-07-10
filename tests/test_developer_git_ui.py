import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
REVIEW_JS = (ROOT / "frontend" / "static" / "review.js").read_text(encoding="utf-8")
APP_JS = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")


class DeveloperGitUiTest(unittest.TestCase):
    def test_commit_push_button_and_backend_preflight_are_wired(self):
        self.assertIn('id="commit-push-button"', HTML)
        self.assertIn('api("/api/git/preflight")', REVIEW_JS)
        self.assertIn('api("/api/git/commit_push"', REVIEW_JS)
        self.assertNotIn('api("/api/commit"', REVIEW_JS)
        self.assertNotIn('api("/api/push"', REVIEW_JS)
        for label in ("Failed rule", "File", "Line", "Detected", "How to fix",
                      "Open Diff", "Ignore Once", "Cancel"):
            self.assertIn(label, HTML + REVIEW_JS)

    def test_new_codex_conversation_button_is_wired(self):
        self.assertIn('id="new-codex-session-button"', HTML)
        self.assertIn('api("/api/developer/session/new"', APP_JS)


if __name__ == "__main__":
    unittest.main()
