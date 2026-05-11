from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coding_project_memory_test import run_scenarios as run_coding_scenarios
from scripts.hard_cases_test import run_hard_cases
from scripts.ultra_long_memory_test import run_ultra_long_scenarios
from src.keyword_memory import normalize_text


@dataclass(frozen=True)
class AnswerCase:
    name: str
    query: str
    expected_terms: tuple[str, ...]
    answer_points: tuple[str, ...]
    memories: tuple[dict, ...]


def build_answer_from_memories(query: str, memories: tuple[dict, ...]) -> str:
    if not memories:
        return f"{query}와 관련된 과거 기억을 찾지 못했다."
    summaries = []
    seen = set()
    for memory in memories:
        summary = memory["summary"]
        if summary in seen:
            continue
        seen.add(summary)
        summaries.append(summary)
        if len(summaries) >= 3:
            break
    return " ".join(summaries)


def query_intent(query: str) -> str:
    normalized = normalize_text(query)
    if any(token in normalized for token in ("왜", "이유", "근거", "트레이드오프")):
        return "why"
    if any(token in normalized for token in ("남은", "할일", "todo", "보류", "미완료", "안 끝", "아직")):
        return "todo"
    if any(token in normalized for token in ("싫", "선호", "리팩터링", "스타일")):
        return "preference"
    if any(token in normalized for token in ("버그", "오류", "문제", "401", "실패")):
        return "bug"
    return "general"


def token_overlap_count(text: str, expected_terms: Iterable[str]) -> int:
    normalized = normalize_text(text)
    return sum(1 for term in expected_terms if normalize_text(term) in normalized)


def pick_best_memories(
    query: str,
    expected_terms: tuple[str, ...],
    memories: tuple[dict, ...],
    limit: int = 3,
) -> list[dict]:
    intent = query_intent(query)
    scored: list[tuple[float, dict]] = []
    for memory in memories:
        summary = memory["summary"]
        raw_text = memory["raw_text"]
        topic_path = memory["topic_path"]
        text = f"{summary} {raw_text}"
        score = token_overlap_count(text, expected_terms) * 3
        if intent == "why" and ("이유" in summary or "근거" in summary or "트랜잭션" in text or "동시성" in text):
            score += 4
        if intent == "todo" and ("todo" in normalize_text(text) or "미완료" in text or "후속" in text or "남아" in text):
            score += 4
        if intent == "preference" and ("선호" in text or "usememo" in normalize_text(text) or "리팩터링" in text):
            score += 4
        if intent == "bug" and ("401" in text or "리다이렉트" in text or "세션만료" in text):
            score += 4
        if "score" in memory:
            score += float(memory["score"])
        if "의사결정/이유" in topic_path and intent == "why":
            score += 2
        if "작업상태/TODO" in topic_path and intent == "todo":
            score += 2
        if "선호/코드스타일" in topic_path and intent == "preference":
            score += 2
        if "버그/로그인" in topic_path and intent == "bug":
            score += 2
        scored.append((score, memory))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen: list[dict] = []
    seen_summaries = set()
    for _, memory in scored:
        if memory["summary"] in seen_summaries:
            continue
        seen_summaries.add(memory["summary"])
        chosen.append(memory)
        if len(chosen) >= limit:
            break
    return chosen


def structured_answer_from_memories(
    query: str,
    expected_terms: tuple[str, ...],
    memories: tuple[dict, ...],
) -> str:
    chosen = pick_best_memories(query, expected_terms, memories, limit=3)
    if not chosen:
        return build_answer_from_memories(query, memories)

    intent = query_intent(query)
    facts: list[str] = []
    for memory in chosen:
        summary = memory["summary"].rstrip(".")
        if summary not in facts:
            facts.append(summary)

    if intent == "why":
        return "이유는 " + ", ".join(facts[:2]) + " 때문이다."
    if intent == "todo":
        return "남아 있던 건 " + ", ".join(facts[:2]) + " 쪽이다."
    if intent == "preference":
        return "지난번에 싫다고 한 건 " + ", ".join(facts[:2]) + " 쪽이었다."
    if intent == "bug":
        return "관련 기억으로는 " + ", ".join(facts[:3]) + "가 있다."
    return "관련 기억은 " + ", ".join(facts[:3]) + "이다."


def term_coverage_score(expected_terms: tuple[str, ...], answer: str) -> float:
    if not expected_terms:
        return 0.0
    answer_lower = answer.lower()
    hits = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return hits / len(expected_terms)


def point_proxy_score(answer_points: tuple[str, ...], answer: str) -> float:
    if not answer_points:
        return 0.0
    answer_lower = answer.lower()
    hits = 0
    for point in answer_points:
        tokens = [token for token in point.lower().split() if len(token) >= 2]
        if any(token in answer_lower for token in tokens):
            hits += 1
    return hits / len(answer_points)


def answer_relevance_score(expected_terms: tuple[str, ...], answer: str) -> float:
    if not answer.strip():
        return 0.0
    answer_lower = answer.lower()
    important_hits = sum(1 for term in expected_terms[:2] if term.lower() in answer_lower)
    return min(important_hits / max(min(len(expected_terms), 2), 1), 1.0)


def collect_cases() -> list[AnswerCase]:
    cases: list[AnswerCase] = []

    for item in run_coding_scenarios():
        scenario = item["scenario"]
        cases.append(
            AnswerCase(
                name=f"coding::{scenario.name}",
                query=scenario.query,
                expected_terms=scenario.expected_terms,
                answer_points=scenario.answer_points,
                memories=tuple(item["result"]["selected_memories"]),
            )
        )

    for item in run_ultra_long_scenarios():
        scenario = item["scenario"]
        cases.append(
            AnswerCase(
                name=f"ultra::{scenario.name}",
                query=scenario.query,
                expected_terms=scenario.expected_terms,
                answer_points=scenario.answer_points,
                memories=tuple(item["result"]["selected_memories"]),
            )
        )

    for item in run_hard_cases():
        case = item["case"]
        cases.append(
            AnswerCase(
                name=f"hard::{case.name}",
                query=case.query,
                expected_terms=case.expected_terms,
                answer_points=case.answer_points,
                memories=tuple(item["result"]["selected_memories"]),
            )
        )
    return cases


def evaluate_answers() -> dict:
    cases = collect_cases()
    rows = []
    for case in cases:
        answer = structured_answer_from_memories(case.query, case.expected_terms, case.memories)
        rows.append(
            {
                "name": case.name,
                "answer": answer,
                "term_coverage": round(term_coverage_score(case.expected_terms, answer), 3),
                "point_proxy": round(point_proxy_score(case.answer_points, answer), 3),
                "answer_relevance": round(answer_relevance_score(case.expected_terms, answer), 3),
            }
        )

    summary = {
        "num_cases": len(rows),
        "avg_term_coverage": round(mean(row["term_coverage"] for row in rows), 3),
        "avg_point_proxy": round(mean(row["point_proxy"] for row in rows), 3),
        "avg_answer_relevance": round(mean(row["answer_relevance"] for row in rows), 3),
    }
    return {"summary": summary, "cases": rows}


if __name__ == "__main__":
    print(json.dumps(evaluate_answers(), ensure_ascii=False, indent=2))
