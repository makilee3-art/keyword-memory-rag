from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.answer_benchmark import (
    AnswerCase,
    answer_relevance_score,
    collect_cases,
    point_proxy_score,
    structured_answer_from_memories,
    term_coverage_score,
)
from scripts.live_chat_test import OpenAIResponsesClient


def llm_answer_from_memories(
    client: OpenAIResponsesClient,
    case: AnswerCase,
) -> str:
    rendered_memories = "\n\n".join(
        [
            f"[{idx + 1}] {memory['timestamp']} {memory['topic_path']}\n"
            f"summary={memory['summary']}\n"
            f"text={memory['raw_text']}"
            for idx, memory in enumerate(case.memories)
        ]
    )
    instructions = textwrap.dedent(
        """
        Answer the user's latest question in Korean using the retrieved project memories.
        Be concise but explicit.
        Prefer mentioning the most decision-relevant details directly.
        If the question asks why, explain the reason.
        If it asks what remains, list remaining items.
        If it asks about preference, state the disliked or preferred approach directly.
        """
    ).strip()
    input_text = textwrap.dedent(
        f"""
        User question:
        {case.query}

        Expected important concepts:
        {", ".join(case.expected_terms)}

        Retrieved memories:
        {rendered_memories or '(none)'}
        """
    ).strip()
    return client.create_text_response(instructions, input_text)


def llm_judge_answer(
    client: OpenAIResponsesClient,
    case: AnswerCase,
    answer: str,
) -> dict[str, Any]:
    instructions = textwrap.dedent(
        """
        You are grading a Korean answer for a memory-retrieval benchmark.
        Return strict json with keys:
        - point_coverage: number from 0 to 1
        - relevance: number from 0 to 1
        - groundedness: number from 0 to 1
        - verdict: short Korean sentence
        Score point_coverage by checking whether the answer satisfies the expected answer points.
        Score relevance by checking whether the answer directly addresses the user's question.
        Score groundedness by checking whether the answer stays within the retrieved memory rather than inventing details.
        """
    ).strip()
    rendered_memories = "\n\n".join(
        [
            f"[{idx + 1}] {memory['timestamp']} {memory['topic_path']}\n"
            f"summary={memory['summary']}\n"
            f"text={memory['raw_text']}"
            for idx, memory in enumerate(case.memories)
        ]
    )
    input_text = textwrap.dedent(
        f"""
        Return json.

        User question:
        {case.query}

        Expected answer points:
        {json.dumps(list(case.answer_points), ensure_ascii=False)}

        Expected important terms:
        {json.dumps(list(case.expected_terms), ensure_ascii=False)}

        Retrieved memories:
        {rendered_memories or '(none)'}

        Candidate answer:
        {answer}
        """
    ).strip()
    return client.create_json_response(instructions, input_text)


def evaluate_answer_text(case: AnswerCase, answer: str) -> dict:
    return {
        "term_coverage": round(term_coverage_score(case.expected_terms, answer), 3),
        "point_proxy": round(point_proxy_score(case.answer_points, answer), 3),
        "answer_relevance": round(answer_relevance_score(case.expected_terms, answer), 3),
    }


def summarize(rows: list[dict]) -> dict:
    return {
        "num_cases": len(rows),
        "avg_term_coverage": round(mean(row["term_coverage"] for row in rows), 3),
        "avg_point_proxy": round(mean(row["point_proxy"] for row in rows), 3),
        "avg_answer_relevance": round(mean(row["answer_relevance"] for row in rows), 3),
    }


def summarize_llm_judge(rows: list[dict]) -> dict:
    return {
        "num_cases": len(rows),
        "avg_point_coverage": round(mean(float(row["point_coverage"]) for row in rows), 3),
        "avg_relevance": round(mean(float(row["relevance"]) for row in rows), 3),
        "avg_groundedness": round(mean(float(row["groundedness"]) for row in rows), 3),
    }


def evaluate_live_answers(client: OpenAIResponsesClient) -> dict:
    cases = collect_cases()
    rows = []
    heuristic_judged = []
    llm_judged = []
    for case in cases:
        heuristic_answer = structured_answer_from_memories(
            case.query,
            case.expected_terms,
            case.memories,
        )
        llm_answer = llm_answer_from_memories(client, case)
        heuristic_scores = evaluate_answer_text(case, heuristic_answer)
        llm_scores = evaluate_answer_text(case, llm_answer)
        heuristic_judge = llm_judge_answer(client, case, heuristic_answer)
        llm_judge = llm_judge_answer(client, case, llm_answer)
        heuristic_judged.append(heuristic_judge)
        llm_judged.append(llm_judge)
        rows.append(
            {
                "name": case.name,
                "heuristic_answer": heuristic_answer,
                "llm_answer": llm_answer,
                "heuristic_scores": heuristic_scores,
                "llm_scores": llm_scores,
                "heuristic_judge": heuristic_judge,
                "llm_judge": llm_judge,
            }
        )

    heuristic_summary = summarize([row["heuristic_scores"] for row in rows])
    llm_summary = summarize([row["llm_scores"] for row in rows])
    heuristic_judge_summary = summarize_llm_judge(heuristic_judged)
    llm_judge_summary = summarize_llm_judge(llm_judged)
    return {
        "heuristic_summary": heuristic_summary,
        "llm_summary": llm_summary,
        "heuristic_judge_summary": heuristic_judge_summary,
        "llm_judge_summary": llm_judge_summary,
        "cases": rows,
    }


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    client = OpenAIResponsesClient(api_key=api_key, model=model)
    print(json.dumps(evaluate_live_answers(client), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
