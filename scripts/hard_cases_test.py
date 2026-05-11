from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coding_project_memory_test import build_coding_store
from src.keyword_memory import retrieve_memories


@dataclass(frozen=True)
class HardCase:
    name: str
    query: str
    expected_topics: tuple[str, ...]
    blocked_topics: tuple[str, ...]
    expected_terms: tuple[str, ...]
    answer_points: tuple[str, ...]


def load_hard_cases() -> list[HardCase]:
    benchmark_path = ROOT / "benchmarks" / "hard_cases.json"
    raw_cases = json.loads(benchmark_path.read_text(encoding="utf-8"))
    return [
        HardCase(
            name=item["name"],
            query=item["query"],
            expected_topics=tuple(item["expected_topics"]),
            blocked_topics=tuple(item.get("blocked_topics", [])),
            expected_terms=tuple(item.get("expected_terms", [])),
            answer_points=tuple(item.get("answer_points", [])),
        )
        for item in raw_cases
    ]


def run_hard_cases() -> list[dict]:
    store = build_coding_store()
    cases = load_hard_cases()
    results = []
    for case in cases:
        result = retrieve_memories(
            store,
            case.query,
            topic_limit=3,
            per_topic_limit=3,
            max_memories=6,
        )
        ranked_paths = [item["path"] for item in result["ranked_topics"]]
        combined_text = " ".join(
            f"{memory['summary']} {memory['raw_text']}" for memory in result["selected_memories"]
        )
        results.append(
            {
                "case": case,
                "ranked_paths": ranked_paths,
                "combined_text": combined_text,
                "result": result,
            }
        )
    return results


if __name__ == "__main__":
    for item in run_hard_cases():
        case = item["case"]
        print(f"== {case.name} ==")
        print("query:", case.query)
        print("ranked_topics:", item["ranked_paths"])
        for memory in item["result"]["selected_memories"]:
            print("-", memory["timestamp"], memory["topic_path"], memory["summary"], memory["score"])
        print()
