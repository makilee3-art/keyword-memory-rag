import unittest

from scripts.answer_benchmark import evaluate_answers


class AnswerBenchmarkTests(unittest.TestCase):
    def test_answer_benchmark_reports_scores(self) -> None:
        result = evaluate_answers()

        self.assertGreaterEqual(result["summary"]["num_cases"], 9)
        self.assertGreater(result["summary"]["avg_term_coverage"], 0.6)
        self.assertGreater(result["summary"]["avg_point_proxy"], 0.45)
        self.assertGreater(result["summary"]["avg_answer_relevance"], 0.65)


if __name__ == "__main__":
    unittest.main()
