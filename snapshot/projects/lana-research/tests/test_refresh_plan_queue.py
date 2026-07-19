import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class RefreshPlanQueueTests(unittest.TestCase):
    def test_selects_only_unseen_sources_up_to_available_slots(self):
        from refresh_plan_queue import select_candidates

        sources = [
            (101, "Fresh market microstructure evidence", "https://example.test/a"),
            (102, "Already queued evidence", "https://example.test/b"),
            (103, "Second fresh source", "https://example.test/c"),
        ]
        selected = select_candidates(sources, {102}, slots=2)
        self.assertEqual([x[0] for x in selected], [101, 103])


if __name__ == "__main__":
    unittest.main()
