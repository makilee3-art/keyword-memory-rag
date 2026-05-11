import unittest

from scripts.coding_project_memory_test import run_scenarios


class CodingProjectMemoryTests(unittest.TestCase):
    def test_coding_project_long_conversation_recall(self) -> None:
        results = run_scenarios()

        for item in results:
            scenario = item["scenario"]
            ranked_paths = item["ranked_paths"]
            combined_text = item["combined_text"]

            for expected_topic in scenario.expected_topics:
                self.assertIn(expected_topic, ranked_paths, msg=scenario.name)

            for blocked_topic in scenario.blocked_topics:
                self.assertNotIn(blocked_topic, ranked_paths[:2], msg=scenario.name)

            matched_terms = [
                term for term in scenario.expected_terms if term.lower() in combined_text.lower()
            ]
            self.assertGreaterEqual(len(matched_terms), 2, msg=scenario.name)


if __name__ == "__main__":
    unittest.main()
