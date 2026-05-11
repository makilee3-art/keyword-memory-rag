import unittest

from scripts.hard_cases_test import run_hard_cases


class HardCasesTests(unittest.TestCase):
    def test_hard_negative_cases(self) -> None:
        results = run_hard_cases()

        for item in results:
            case = item["case"]
            ranked_paths = item["ranked_paths"]
            combined_text = item["combined_text"].lower()

            for expected_topic in case.expected_topics:
                self.assertIn(expected_topic, ranked_paths, msg=case.name)

            for blocked_topic in case.blocked_topics:
                self.assertNotIn(blocked_topic, ranked_paths[:2], msg=case.name)

            matched_terms = [term for term in case.expected_terms if term.lower() in combined_text]
            self.assertGreaterEqual(len(matched_terms), 2, msg=case.name)


if __name__ == "__main__":
    unittest.main()
