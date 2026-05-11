from __future__ import annotations

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.keyword_memory import KeywordMemoryStore, MemoryChunk, isoformat, retrieve_memories


@dataclass(frozen=True)
class CodingScenario:
    name: str
    query: str
    expected_topics: tuple[str, ...]
    expected_terms: tuple[str, ...]
    blocked_topics: tuple[str, ...] = ()
    answer_points: tuple[str, ...] = ()


CODING_TOPICS = (
    ("프로젝트/아키텍처/인증", "로그인 인증 세션 토큰 권한 구조 설계", ("로그인", "인증", "세션", "JWT", "권한")),
    ("프로젝트/아키텍처/데이터베이스", "sqlite postgres 마이그레이션 스키마 트랜잭션", ("sqlite", "postgres", "db", "마이그레이션", "스키마")),
    ("프로젝트/버그/로그인", "로그인 버그 쿠키 세션 만료 리다이렉트 오류", ("로그인버그", "쿠키", "세션만료", "리다이렉트", "401")),
    ("프로젝트/작업상태/TODO", "보류 작업 TODO 다음 단계 미완료 계획 남은 할일", ("todo", "보류", "다음단계", "미완료", "추가작업", "할일")),
    ("프로젝트/선호/코드스타일", "리팩터링 선호 코드스타일 훅 분리 금지사항", ("리팩터링", "코드스타일", "선호", "금지", "훅분리")),
    ("프로젝트/의사결정/이유", "왜 그렇게 했는지 결정 근거 트레이드오프", ("결정", "이유", "근거", "트레이드오프")),
)


def build_coding_store() -> KeywordMemoryStore:
    store = KeywordMemoryStore.create()
    store.initialize()

    for path, description, keywords in CODING_TOPICS:
        store.connection.execute(
            "INSERT OR IGNORE INTO topics(path, description) VALUES(?, ?)",
            (path, description),
        )
        topic_id = store.connection.execute(
            "SELECT id FROM topics WHERE path = ?",
            (path,),
        ).fetchone()["id"]
        for keyword in keywords:
            store.connection.execute(
                "INSERT OR IGNORE INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
                (keyword, topic_id),
            )
    store.connection.commit()

    now = datetime(2026, 5, 11, 22, 0, 0)
    chunks = [
        MemoryChunk(
            raw_text=(
                "user: 로그인 구현은 일단 세션 쿠키 기반으로 가자. JWT는 지금 단계에선 과하다.\n"
                "assistant: 인증 구조는 서버 세션과 쿠키로 유지하기로 결정."
            ),
            summary="로그인 인증은 JWT 대신 세션 쿠키로 가기로 함",
            timestamp=isoformat(now - timedelta(days=120)),
            topic_paths=("프로젝트/아키텍처/인증", "프로젝트/의사결정/이유"),
            keywords=("로그인", "인증", "세션", "쿠키", "결정", "이유"),
            salience=0.9,
        ),
        MemoryChunk(
            raw_text=(
                "user: 처음엔 sqlite로 빠르게 가고, 배포 전엔 postgres로 옮기자.\n"
                "assistant: 개발 속도 때문에 sqlite를 먼저 쓰고 이후 postgres로 마이그레이션."
            ),
            summary="개발 초기엔 sqlite, 운영 전환 시 postgres로 이동",
            timestamp=isoformat(now - timedelta(days=110)),
            topic_paths=("프로젝트/아키텍처/데이터베이스", "프로젝트/의사결정/이유"),
            keywords=("sqlite", "postgres", "마이그레이션", "결정", "트레이드오프"),
            salience=0.85,
        ),
        MemoryChunk(
            raw_text=(
                "user: 로그인 후 새로고침하면 가끔 401이 뜬다.\n"
                "assistant: 세션 만료 처리와 리다이렉트 흐름에 버그가 있어 보인다."
            ),
            summary="새로고침 후 401이 뜨는 로그인 버그 기록",
            timestamp=isoformat(now - timedelta(days=75)),
            topic_paths=("프로젝트/버그/로그인", "프로젝트/아키텍처/인증"),
            keywords=("로그인버그", "401", "세션만료", "리다이렉트", "인증"),
            salience=0.95,
        ),
        MemoryChunk(
            raw_text=(
                "user: useMemo, useCallback 남발하는 리팩터링은 싫어. 읽기 더 어려워져.\n"
                "assistant: 과한 메모이제이션 스타일은 피하고 단순한 구조를 선호."
            ),
            summary="과한 메모이제이션 리팩터링은 피하기로 함",
            timestamp=isoformat(now - timedelta(days=60)),
            topic_paths=("프로젝트/선호/코드스타일",),
            keywords=("리팩터링", "코드스타일", "선호", "금지", "useMemo"),
            salience=0.88,
        ),
        MemoryChunk(
            raw_text=(
                "user: 로그인 버그 고치고 나면 csrf 정리와 테스트 추가는 TODO로 남겨두자.\n"
                "assistant: csrf 정리와 인증 테스트 확장은 후속 작업으로 보류."
            ),
            summary="csrf 정리와 인증 테스트는 후속 TODO",
            timestamp=isoformat(now - timedelta(days=45)),
            topic_paths=("프로젝트/작업상태/TODO", "프로젝트/아키텍처/인증"),
            keywords=("todo", "보류", "csrf", "테스트", "인증"),
            salience=0.8,
        ),
        MemoryChunk(
            raw_text=(
                "user: sqlite는 동시성 쪽이 불안해서 결국 postgres로 가야 할 것 같아.\n"
                "assistant: 운영 환경 동시성과 트랜잭션 안정성 때문에 postgres 전환 근거를 확인."
            ),
            summary="postgres 전환 이유는 동시성과 트랜잭션 안정성",
            timestamp=isoformat(now - timedelta(days=20)),
            topic_paths=("프로젝트/아키텍처/데이터베이스", "프로젝트/의사결정/이유"),
            keywords=("sqlite", "postgres", "동시성", "트랜잭션", "근거"),
            salience=0.93,
        ),
        MemoryChunk(
            raw_text=(
                "user: 로그인 쪽은 고쳤는데 쿠키 만료 후 리다이렉트가 아직 어색해.\n"
                "assistant: 로그인 버그는 완전히 끝난 게 아니라 쿠키 만료 UX가 남아 있음."
            ),
            summary="쿠키 만료 후 리다이렉트 UX 이슈가 남아 있음",
            timestamp=isoformat(now - timedelta(days=10)),
            topic_paths=("프로젝트/버그/로그인", "프로젝트/작업상태/TODO"),
            keywords=("로그인버그", "쿠키", "리다이렉트", "todo", "미완료"),
            salience=0.91,
        ),
    ]

    for chunk in chunks:
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
    return store


def run_scenarios() -> list[dict]:
    store = build_coding_store()
    benchmark_path = ROOT / "benchmarks" / "coding_project_cases.json"
    raw_cases = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [
        CodingScenario(
            name=item["name"],
            query=item["query"],
            expected_topics=tuple(item["expected_topics"]),
            expected_terms=tuple(item["expected_terms"]),
            blocked_topics=tuple(item.get("blocked_topics", [])),
            answer_points=tuple(item.get("answer_points", [])),
        )
        for item in raw_cases
    ]

    results: list[dict] = []
    for scenario in scenarios:
        result = retrieve_memories(
            store,
            scenario.query,
            topic_limit=3,
            per_topic_limit=3,
            max_memories=6,
        )
        combined_text = " ".join(
            f"{item['summary']} {item['raw_text']}" for item in result["selected_memories"]
        )
        ranked_paths = [item["path"] for item in result["ranked_topics"]]
        results.append(
            {
                "scenario": scenario,
                "ranked_paths": ranked_paths,
                "combined_text": combined_text,
                "result": result,
            }
        )
    return results


if __name__ == "__main__":
    for item in run_scenarios():
        scenario = item["scenario"]
        print(f"== {scenario.name} ==")
        print("query:", scenario.query)
        print("ranked_topics:", item["ranked_paths"])
        for memory in item["result"]["selected_memories"]:
            print("-", memory["timestamp"], memory["topic_path"], memory["summary"])
        print()
