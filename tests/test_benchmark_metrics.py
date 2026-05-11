import unittest

from scripts.benchmark_metrics import evaluate_cases


class BenchmarkMetricsTests(unittest.TestCase):
    def test_benchmark_metrics_are_reported(self) -> None:
        result = evaluate_cases()

        self.assertGreaterEqual(result["summary"]["num_cases"], 6)
        self.assertGreater(result["summary"]["avg_recall_at_3"], 0.5)
        self.assertGreater(result["summary"]["avg_precision_at_3"], 0.4)
        self.assertGreater(result["summary"]["avg_mrr"], 0.5)
        self.assertGreater(result["summary"]["avg_topic_diversity"], 0.5)


if __name__ == "__main__":
    unittest.main()
