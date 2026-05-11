from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coding_project_memory_test import run_scenarios as run_coding_scenarios
from scripts.hard_cases_test import run_hard_cases
from scripts.ultra_long_memory_test import run_ultra_long_scenarios


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    expected_topics: tuple[str, ...]
    ranked_topics: tuple[str, ...]
    blocked_topics: tuple[str, ...] = ()


def recall_at_k(expected: tuple[str, ...], ranked: tuple[str, ...], k: int) -> float:
    if not expected:
        return 0.0
    top_k = set(ranked[:k])
    hits = sum(1 for item in expected if item in top_k)
    return hits / len(expected)


def precision_at_k(expected: tuple[str, ...], ranked: tuple[str, ...], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = ranked[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in expected)
    return hits / len(top_k)


def mrr(expected: tuple[str, ...], ranked: tuple[str, ...]) -> float:
    for index, item in enumerate(ranked, start=1):
        if item in expected:
            return 1.0 / index
    return 0.0


def topic_diversity(ranked: tuple[str, ...]) -> float:
    if not ranked:
        return 0.0
    return len(set(ranked)) / len(ranked)


def blocked_topic_rate(blocked: tuple[str, ...], ranked: tuple[str, ...], k: int) -> float:
    if not blocked:
        return 0.0
    top_k = ranked[:k]
    hits = sum(1 for item in top_k if item in blocked)
    return hits / len(top_k) if top_k else 0.0


def build_cases() -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for item in run_coding_scenarios():
        scenario = item["scenario"]
        cases.append(
            BenchmarkCase(
                name=f"coding::{scenario.name}",
                expected_topics=scenario.expected_topics,
                ranked_topics=tuple(item["ranked_paths"]),
                blocked_topics=tuple(getattr(scenario, "blocked_topics", ())),
            )
        )
    for item in run_ultra_long_scenarios():
        scenario = item["scenario"]
        cases.append(
            BenchmarkCase(
                name=f"ultra::{scenario.name}",
                expected_topics=scenario.expected_topics,
                ranked_topics=tuple(item["ranked_paths"]),
                blocked_topics=tuple(getattr(scenario, "blocked_topics", ())),
            )
        )
    for item in run_hard_cases():
        case = item["case"]
        cases.append(
            BenchmarkCase(
                name=f"hard::{case.name}",
                expected_topics=case.expected_topics,
                ranked_topics=tuple(item["ranked_paths"]),
                blocked_topics=case.blocked_topics,
            )
        )
    return cases


def evaluate_cases() -> dict:
    cases = build_cases()
    per_case = []
    for case in cases:
        per_case.append(
            {
                "name": case.name,
                "recall_at_3": round(recall_at_k(case.expected_topics, case.ranked_topics, 3), 3),
                "precision_at_3": round(precision_at_k(case.expected_topics, case.ranked_topics, 3), 3),
                "mrr": round(mrr(case.expected_topics, case.ranked_topics), 3),
                "topic_diversity": round(topic_diversity(case.ranked_topics), 3),
                "blocked_topic_rate_at_3": round(blocked_topic_rate(case.blocked_topics, case.ranked_topics, 3), 3),
            }
        )

    summary = {
        "num_cases": len(per_case),
        "avg_recall_at_3": round(mean(item["recall_at_3"] for item in per_case), 3),
        "avg_precision_at_3": round(mean(item["precision_at_3"] for item in per_case), 3),
        "avg_mrr": round(mean(item["mrr"] for item in per_case), 3),
        "avg_topic_diversity": round(mean(item["topic_diversity"] for item in per_case), 3),
        "avg_blocked_topic_rate_at_3": round(mean(item["blocked_topic_rate_at_3"] for item in per_case), 3),
    }
    return {"summary": summary, "cases": per_case}


if __name__ == "__main__":
    import json

    print(json.dumps(evaluate_cases(), ensure_ascii=False, indent=2))
