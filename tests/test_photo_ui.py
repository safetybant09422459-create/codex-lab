from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PhotoUiTest(unittest.TestCase):
    def test_photo_screen_is_a_real_lazy_loaded_read_experience(self) -> None:
        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "static" / "photo.js").read_text(encoding="utf-8")

        self.assertIn('id="photo-summary"', html)
        self.assertIn('src="/static/photo.js"', html)
        self.assertIn('"/api/photo/recent-summary?days="', source)
        self.assertIn('event.detail.screenId === "photo-screen"', source)
        self.assertNotIn("asset_id", source)
        self.assertNotIn("sample_photo_ids", source)

    def test_consumer_shell_does_not_eagerly_load_developer_apis(self) -> None:
        source = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

        initializer = source.index("function initializeDeveloperScreen()")
        initial_load_call = source.index("Promise.allSettled", initializer)
        screen_guard = source.index('screenId === "developer-screen"')
        self.assertGreater(initial_load_call, initializer)
        self.assertGreater(screen_guard, initial_load_call)


if __name__ == "__main__":
    unittest.main()
