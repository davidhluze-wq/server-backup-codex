import unittest
from pathlib import Path


class LanaAuthResponseTests(unittest.TestCase):
    def test_unauthenticated_response_is_explanatory_html(self):
        source = Path("scripts/server.py").read_text(encoding="utf-8")
        self.assertIn("Přihlášení je vyžadováno", source)
        self.assertIn('"Content-Type", "text/html; charset=utf-8"', source)


if __name__ == "__main__":
    unittest.main()
