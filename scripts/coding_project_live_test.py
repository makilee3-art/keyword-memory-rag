from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.keyword_memory import KeywordMemoryStore, MemoryChunk, isoformat
from scripts.live_chat_test import (
    OpenAIResponsesClient,
    answer_query,
    decide_continue,
    normalize_keywords,
)
from src.keyword_memory import tokenize


CODING_TOPIC_SEEDS = (
    {
        "path": "프로젝트/아키텍처/인증",
        "description": "로그인 인증 세션 토큰 권한 구조 설계",
        "keywords": ("로그인", "인증", "세션", "JWT", "권한", "쿠키"),
    },
    {
        "path": "프로젝트/아키텍처/데이터베이스",
        "description": "sqlite postgres 마이그레이션 스키마 트랜잭션",
        "keywords": ("sqlite", "postgres", "db", "마이그레이션", "스키마", "트랜잭션"),
    },
    {
        "path": "프로젝트/버그/로그인",
        "description": "로그인 버그 쿠키 세션 만료 리다이렉트 오류 401",
        "keywords": ("로그인버그", "쿠키", "세션만료", "리다이렉트", "401"),
    },
    {
        "path": "프로젝트/작업상태/TODO",
        "description": "보류 작업 TODO 다음 단계 미완료 계획 남은 할일",
        "keywords": ("todo", "보류", "다음단계", "미완료", "추가작업", "할일"),
    },
    {
        "path": "프로젝트/선호/코드스타일",
        "description": "리팩터링 선호 코드스타일 훅 분리 금지사항",
        "keywords": ("리팩터링", "코드스타일", "선호", "금지", "훅분리", "useMemo", "useCallback"),
    },
    {
        "path": "프로젝트/의사결정/이유",
        "description": "왜 그렇게 했는지 결정 근거 트레이드오프",
        "keywords": ("결정", "이유", "근거", "트레이드오프"),
    },
)

CODING_RELATED_TOPICS = {
    "프로젝트/버그/로그인": (
        "프로젝트/아키텍처/인증",
        "프로젝트/작업상태/TODO",
    ),
    "프로젝트/아키텍처/데이터베이스": (
        "프로젝트/의사결정/이유",
    ),
    "프로젝트/작업상태/TODO": (
        "프로젝트/아키텍처/인증",
    ),
}


def coding_topic_catalog_text() -> str:
    return "\n".join(
        f"- {seed['path']}: {seed['description']} | keywords={', '.join(seed['keywords'])}"
        for seed in CODING_TOPIC_SEEDS
    )


def normalize_coding_topic_paths(candidate_paths, raw_text: str) -> tuple[str, ...]:
    allowed_paths = [seed["path"] for seed in CODING_TOPIC_SEEDS]
    normalized = []

    for candidate in candidate_paths:
        candidate_clean = str(candidate).strip()
        if candidate_clean in allowed_paths:
            normalized.append(candidate_clean)
            continue
        candidate_tail = candidate_clean.split("/")[-1]
        for allowed in allowed_paths:
            if candidate_clean in allowed or allowed in candidate_clean:
                normalized.append(allowed)
                break
            if candidate_tail and candidate_tail == allowed.split("/")[-1]:
                normalized.append(allowed)
                break

    if normalized:
        return tuple(dict.fromkeys(normalized))

    text_tokens = tokenize(raw_text)
    fallback = []
    for seed in CODING_TOPIC_SEEDS:
        overlap = len(text_tokens & tokenize(seed["description"] + " " + " ".join(seed["keywords"])))
        if overlap > 0:
            fallback.append(seed["path"])
    return tuple(fallback[:3])


def create_coding_store() -> KeywordMemoryStore:
    store = KeywordMemoryStore.create()
    for seed in CODING_TOPIC_SEEDS:
        store.connection.execute(
            "INSERT OR IGNORE INTO topics(path, description) VALUES(?, ?)",
            (seed["path"], seed["description"]),
        )
        topic_id = store.connection.execute(
            "SELECT id FROM topics WHERE path = ?",
            (seed["path"],),
        ).fetchone()["id"]
        for keyword in seed["keywords"]:
            store.connection.execute(
                "INSERT OR IGNORE INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
                (keyword, topic_id),
            )
    store.connection.commit()
    return store


def extract_coding_memory_chunk(
    client: OpenAIResponsesClient,
    transcript_block: str,
    timestamp: str,
) -> MemoryChunk:
    instructions = (
        "You convert an old coding-project conversation block into structured memory. "
        "Return strict json with keys: summary, topic_paths, keywords, salience. "
        "summary is a short Korean summary. "
        "topic_paths must be chosen only from the provided catalog. "
        "keywords must be 3 to 8 grounded terms from the text. "
        "salience is a number from 0 to 1."
    )
    input_text = (
        f"Return json.\n\n"
        f"Topic catalog:\n{coding_topic_catalog_text()}\n\n"
        f"Conversation block:\n{transcript_block}"
    )
    data = client.create_json_response(instructions, input_text)
    topic_paths = normalize_coding_topic_paths(
        data.get("topic_paths", []),
        transcript_block,
    )
    allowed = {seed["path"] for seed in CODING_TOPIC_SEEDS}
    topic_paths = tuple(path for path in topic_paths if path in allowed)
    keywords = normalize_keywords(data.get("keywords", []), transcript_block)
    if not topic_paths:
        raise RuntimeError(f"Model did not return usable coding topic paths: {json.dumps(data, ensure_ascii=False)}")
    if not keywords:
        raise RuntimeError(f"Model did not return usable coding keywords: {json.dumps(data, ensure_ascii=False)}")
    return MemoryChunk(
        raw_text=transcript_block,
        summary=str(data["summary"]).strip(),
        timestamp=timestamp,
        topic_paths=topic_paths,
        keywords=keywords,
        salience=float(data.get("salience", 0.5)),
    )


def save_coding_memory(
    store: KeywordMemoryStore,
    client: OpenAIResponsesClient,
    transcript_block: str,
    timestamp: str,
) -> MemoryChunk:
    chunk = extract_coding_memory_chunk(client, transcript_block, timestamp)
    primary_topic_id = store.connection.execute(
        "SELECT id FROM topics WHERE path = ?",
        (chunk.topic_paths[0],),
    ).fetchone()["id"]
    for keyword in chunk.keywords:
        store.connection.execute(
            "INSERT OR IGNORE INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
            (keyword, primary_topic_id),
        )
    store.connection.commit()
    store.save_memory(chunk)
    return chunk


def choose_coding_topics(
    client: OpenAIResponsesClient,
    query: str,
    max_topics: int = 3,
):
    instructions = (
        "You select which coding-project memory topics should be explored for a new user query. "
        "Return strict json with topics: array of objects {topic_path, reason, score}. "
        "Choose only from the provided catalog. "
        "Use the full query meaning, not keyword extraction."
    )
    input_text = (
        f"Return json.\n\n"
        f"Topic catalog:\n{coding_topic_catalog_text()}\n\n"
        f"User query:\n{query}\n\n"
        f"Select up to {max_topics} topics."
    )
    data = client.create_json_response(instructions, input_text)
    allowed = {seed["path"] for seed in CODING_TOPIC_SEEDS}
    topics = []
    seen = set()
    for item in data.get("topics", []):
        normalized = normalize_coding_topic_paths([item.get("topic_path", "")], query)
        if not normalized:
            continue
        path = normalized[0]
        if path not in allowed or path in seen:
            continue
        seen.add(path)
        topics.append(
            {
                "topic_path": path,
                "reason": str(item.get("reason", "관련 토픽")),
                "score": int(item.get("score", 1)),
            }
        )
        if len(topics) >= max_topics:
            break
    return topics


def retrieve_coding_memories(
    store: KeywordMemoryStore,
    client: OpenAIResponsesClient,
    query: str,
    per_topic_limit: int = 3,
    max_memories: int = 6,
):
    chosen_topics = choose_coding_topics(client, query)
    expanded_topics = []
    seen_paths = set()
    for topic in chosen_topics:
        if topic["topic_path"] not in seen_paths:
            expanded_topics.append(topic)
            seen_paths.add(topic["topic_path"])
        for related_path in CODING_RELATED_TOPICS.get(topic["topic_path"], ()):
            if related_path in seen_paths:
                continue
            expanded_topics.append(
                {
                    "topic_path": related_path,
                    "reason": f"{topic['topic_path']}에서 연관 토픽 확장",
                    "score": max(topic["score"] - 1, 1),
                }
            )
            seen_paths.add(related_path)

    traces = []
    collected = []
    for topic in expanded_topics:
        topic_row = store.get_topic_by_path(topic["topic_path"])
        if topic_row is None:
            continue
        conversations = store.get_recent_conversations_for_topic(
            topic_row["id"], limit=per_topic_limit
        )
        for conversation in conversations:
            memory = {
                "topic_path": topic["topic_path"],
                "conversation_id": conversation["id"],
                "timestamp": conversation["ts"],
                "summary": conversation["summary"],
                "raw_text": conversation["raw_text"],
            }
            collected.append(memory)
            decision = decide_continue(client, query, collected)
            enough_now = decision.enough and not decision.missing_info
            traces.append(
                {
                    "topic_path": topic["topic_path"],
                    "reason": topic["reason"],
                    "score": topic["score"],
                    "conversation_id": conversation["id"],
                    "timestamp": conversation["ts"],
                    "continue_reason": decision.reason,
                    "enough": enough_now,
                    "missing_info": decision.missing_info,
                }
            )
            if enough_now or len(collected) >= max_memories:
                return expanded_topics, collected, traces
    return expanded_topics, collected, traces


def run_coding_demo() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAIResponsesClient(api_key=api_key)
    store = create_coding_store()

    now = datetime(2026, 5, 11, 22, 30, 0)
    transcript_blocks = [
        (
            "user: 로그인 구현은 일단 세션 쿠키 기반으로 가자. JWT는 지금 단계에선 과하다.\n"
            "assistant: 인증 구조는 서버 세션과 쿠키로 유지하기로 결정.",
            isoformat(now - timedelta(days=120)),
        ),
        (
            "user: 처음엔 sqlite로 빠르게 가고, 배포 전엔 postgres로 옮기자.\n"
            "assistant: 개발 속도 때문에 sqlite를 먼저 쓰고 이후 postgres로 마이그레이션.",
            isoformat(now - timedelta(days=110)),
        ),
        (
            "user: 로그인 후 새로고침하면 가끔 401이 뜬다.\n"
            "assistant: 세션 만료 처리와 리다이렉트 흐름에 버그가 있어 보인다.",
            isoformat(now - timedelta(days=75)),
        ),
        (
            "user: useMemo, useCallback 남발하는 리팩터링은 싫어. 읽기 더 어려워져.\n"
            "assistant: 과한 메모이제이션 스타일은 피하고 단순한 구조를 선호.",
            isoformat(now - timedelta(days=60)),
        ),
        (
            "user: 로그인 버그 고치고 나면 csrf 정리와 테스트 추가는 TODO로 남겨두자.\n"
            "assistant: csrf 정리와 인증 테스트 확장은 후속 작업으로 보류.",
            isoformat(now - timedelta(days=45)),
        ),
        (
            "user: sqlite는 동시성 쪽이 불안해서 결국 postgres로 가야 할 것 같아.\n"
            "assistant: 운영 환경 동시성과 트랜잭션 안정성 때문에 postgres 전환 근거를 확인.",
            isoformat(now - timedelta(days=20)),
        ),
        (
            "user: 로그인 쪽은 고쳤는데 쿠키 만료 후 리다이렉트가 아직 어색해.\n"
            "assistant: 로그인 버그는 완전히 끝난 게 아니라 쿠키 만료 UX가 남아 있음.",
            isoformat(now - timedelta(days=10)),
        ),
    ]

    print("== Step 1. Save coding-project conversations with LLM extraction ==")
    for transcript, timestamp in transcript_blocks:
        chunk = save_coding_memory(store, client, transcript, timestamp)
        print(json.dumps(asdict(chunk), ensure_ascii=False, indent=2))

    scenarios = [
        "그 인증 버그 다시 보자",
        "우리가 왜 sqlite 말고 postgres로 가기로 했지?",
        "지난번에 싫다고 한 리팩터링 방식 뭐였지?",
        "인증 쪽 아직 남은 할일 있었나?",
    ]

    for query in scenarios:
        print(f"\n== Query: {query} ==")
        chosen_topics, collected, traces = retrieve_coding_memories(store, client, query)
        print("-- topics --")
        print(json.dumps(chosen_topics, ensure_ascii=False, indent=2))
        print("-- traversal --")
        print(json.dumps(traces, ensure_ascii=False, indent=2))
        print("-- final answer --")
        print(answer_query(client, query, collected))


if __name__ == "__main__":
    run_coding_demo()
