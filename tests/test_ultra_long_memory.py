import unittest

from scripts.ultra_long_memory_test import run_ultra_long_scenarios


class UltraLongMemoryTests(unittest.TestCase):
    def test_ultra_long_keyword_heavy_retrieval(self) -> None:
        results = run_ultra_long_scenarios()

        for item in results:
            scenario = item["scenario"]
            ranked_paths = item["ranked_paths"]
            combined_text = item["combined_text"].lower()

            for expected_topic in scenario.expected_topics:
                self.assertIn(expected_topic, ranked_paths, msg=scenario.name)

            matched_terms = [term for term in scenario.expected_terms if term.lower() in combined_text]
            self.assertGreaterEqual(len(matched_terms), 2, msg=scenario.name)

            blocked_hits = [term for term in scenario.blocked_terms if term.lower() in combined_text]
            self.assertLessEqual(len(blocked_hits), 1, msg=scenario.name)


if __name__ == "__main__":
    unittest.main()
