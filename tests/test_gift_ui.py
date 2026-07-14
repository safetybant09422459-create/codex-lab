from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GiftUiTest(unittest.TestCase):
    def test_gift_screen_and_independent_module_exist(self) -> None:
        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "static" / "gift.js").read_text(encoding="utf-8")
        self.assertIn('id="gift-screen"', html)
        self.assertIn('src="/static/gift.js"', html)
        self.assertIn('"/api/gifts"', source)
        self.assertIn('screenId === "gift-screen"', source)
        self.assertIn("window.confirm", source)
        self.assertNotIn("innerHTML", source)


if __name__ == "__main__":
    unittest.main()
