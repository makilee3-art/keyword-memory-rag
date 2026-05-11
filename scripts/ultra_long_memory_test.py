from __future__ import annotations

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.keyword_memory import KeywordMemoryStore, MemoryChunk, isoformat, tokenize


ULTRA_TOPICS = (
    (
        "프로젝트/아키텍처/인증",
        "로그인 인증 세션 쿠키 토큰 권한 oauth 소셜로그인 접근제어",
        ("로그인", "인증", "세션", "쿠키", "토큰", "권한", "oauth", "소셜로그인"),
    ),
    (
        "프로젝트/버그/로그인",
        "로그인 버그 세션만료 401 리다이렉트 새로고침 에러 인증실패",
        ("로그인버그", "세션만료", "401", "리다이렉트", "새로고침", "에러", "인증실패"),
    ),
    (
        "프로젝트/작업상태/TODO",
        "남은 할일 보류 TODO 미완료 후속작업 추가작업 체크리스트",
        ("todo", "보류", "미완료", "후속작업", "추가작업", "할일", "체크리스트"),
    ),
    (
        "프로젝트/의사결정/이유",
        "왜 그렇게 했는지 이유 결정 근거 트레이드오프 비교 선택",
        ("결정", "이유", "근거", "트레이드오프", "비교", "선택"),
    ),
    (
        "프로젝트/아키텍처/데이터베이스",
        "sqlite postgres mysql 데이터베이스 마이그레이션 스키마 트랜잭션 동시성",
        ("sqlite", "postgres", "mysql", "db", "마이그레이션", "스키마", "트랜잭션", "동시성"),
    ),
    (
        "프로젝트/성능/프론트엔드",
        "렌더링 지연 번들사이즈 hydration lazyloading 메모이제이션",
        ("렌더링", "지연", "번들", "hydration", "lazyloading", "useMemo", "useCallback"),
    ),
    (
        "프로젝트/선호/코드스타일",
        "코드스타일 리팩터링 선호 가독성 단순구조 금지사항",
        ("리팩터링", "코드스타일", "선호", "가독성", "단순구조", "금지"),
    ),
    (
        "프로젝트/배포/인프라",
        "docker ci cd nginx vercel railway 배포 인프라 환경변수",
        ("docker", "ci", "cd", "nginx", "vercel", "railway", "배포", "환경변수"),
    ),
    (
        "프로젝트/관측성/로그",
        "로그 모니터링 sentry tracing metrics alert 에러추적",
        ("로그", "모니터링", "sentry", "tracing", "metrics", "alert", "에러추적"),
    ),
    (
        "프로젝트/테스트/품질",
        "테스트 e2e unit integration qa 회귀 테스트커버리지",
        ("테스트", "e2e", "unit", "integration", "qa", "회귀", "커버리지"),
    ),
)

RELATED_TOPICS = {
    "프로젝트/버그/로그인": (
        "프로젝트/아키텍처/인증",
        "프로젝트/작업상태/TODO",
        "프로젝트/관측성/로그",
    ),
    "프로젝트/아키텍처/인증": (
        "프로젝트/버그/로그인",
        "프로젝트/작업상태/TODO",
    ),
    "프로젝트/아키텍처/데이터베이스": (
        "프로젝트/의사결정/이유",
    ),
}


@dataclass(frozen=True)
class UltraScenario:
    name: str
    query: str
    expected_topics: tuple[str, ...]
    expected_terms: tuple[str, ...]
    blocked_terms: tuple[str, ...]
    blocked_topics: tuple[str, ...] = ()
    answer_points: tuple[str, ...] = ()


def build_ultra_long_store() -> KeywordMemoryStore:
    store = KeywordMemoryStore.create()
    for path, description, keywords in ULTRA_TOPICS:
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

    now = datetime(2026, 5, 11, 23, 0, 0)
    chunks: list[MemoryChunk] = []

    # Core auth/history thread spread across a long horizon.
    chunks.extend(
        [
            MemoryChunk(
                raw_text="user: 인증은 JWT보다 서버 세션 쿠키로 시작하자. assistant: 세션 쿠키 기반으로 결정.",
                summary="초기 인증 구조는 세션 쿠키 기반으로 결정",
                timestamp=isoformat(now - timedelta(days=360)),
                topic_paths=("프로젝트/아키텍처/인증", "프로젝트/의사결정/이유"),
                keywords=("인증", "세션", "쿠키", "결정"),
                salience=0.95,
            ),
            MemoryChunk(
                raw_text="user: oauth 소셜로그인은 나중으로 미루자. assistant: 기본 로그인 먼저 구현하고 oauth는 보류.",
                summary="oauth 소셜로그인은 후속 TODO로 보류",
                timestamp=isoformat(now - timedelta(days=320)),
                topic_paths=("프로젝트/아키텍처/인증", "프로젝트/작업상태/TODO"),
                keywords=("oauth", "소셜로그인", "todo", "보류"),
                salience=0.72,
            ),
            MemoryChunk(
                raw_text="user: 로그인 새로고침 뒤 401이 간헐적으로 난다. assistant: 세션 만료와 리다이렉트 흐름 확인 필요.",
                summary="로그인 새로고침 뒤 401과 세션 만료 버그 기록",
                timestamp=isoformat(now - timedelta(days=280)),
                topic_paths=("프로젝트/버그/로그인", "프로젝트/아키텍처/인증"),
                keywords=("로그인버그", "401", "세션만료", "리다이렉트"),
                salience=0.97,
            ),
            MemoryChunk(
                raw_text="user: 인증 실패 로그를 sentry로 남겨보자. assistant: 로그인 에러추적을 sentry에 연결.",
                summary="인증 실패 로그를 sentry로 관측하기 시작",
                timestamp=isoformat(now - timedelta(days=250)),
                topic_paths=("프로젝트/관측성/로그", "프로젝트/버그/로그인"),
                keywords=("sentry", "로그", "에러추적", "인증실패"),
                salience=0.64,
            ),
            MemoryChunk(
                raw_text="user: 로그인 버그 고치고 csrf 정리랑 인증 테스트는 남겨두자. assistant: 인증 후속 TODO로 남김.",
                summary="csrf 정리와 인증 테스트는 후속 TODO",
                timestamp=isoformat(now - timedelta(days=210)),
                topic_paths=("프로젝트/작업상태/TODO", "프로젝트/아키텍처/인증", "프로젝트/테스트/품질"),
                keywords=("csrf", "테스트", "todo", "후속작업", "인증"),
                salience=0.9,
            ),
            MemoryChunk(
                raw_text="user: 쿠키 만료 뒤 로그인 화면으로 튕기는데 return url이 안 남아. assistant: 리다이렉트 UX 보강 필요.",
                summary="쿠키 만료 후 return url이 사라지는 리다이렉트 UX 이슈",
                timestamp=isoformat(now - timedelta(days=120)),
                topic_paths=("프로젝트/버그/로그인", "프로젝트/작업상태/TODO"),
                keywords=("쿠키", "세션만료", "리다이렉트", "todo", "returnurl"),
                salience=0.92,
            ),
            MemoryChunk(
                raw_text="user: useMemo 남발은 피하자. assistant: 인증 페이지 리팩터링도 단순 구조 선호.",
                summary="인증 페이지도 과한 메모이제이션보다 단순 구조 선호",
                timestamp=isoformat(now - timedelta(days=45)),
                topic_paths=("프로젝트/선호/코드스타일",),
                keywords=("useMemo", "리팩터링", "단순구조", "선호"),
                salience=0.51,
            ),
            MemoryChunk(
                raw_text="user: 로그인은 고쳤는데 세션 만료 시 복귀 동선이 아직 어색해. assistant: 인증 버그는 완전히 끝난 건 아님.",
                summary="세션 만료 후 복귀 동선이 어색한 최신 인증 버그 상태",
                timestamp=isoformat(now - timedelta(days=8)),
                topic_paths=("프로젝트/버그/로그인", "프로젝트/작업상태/TODO"),
                keywords=("로그인버그", "세션만료", "리다이렉트", "미완료"),
                salience=0.96,
            ),
            MemoryChunk(
                raw_text="user: sqlite는 운영 동시성이 약해서 postgres로 가야 해. assistant: 동시성과 트랜잭션 안정성이 전환 이유.",
                summary="postgres 전환 이유는 동시성과 트랜잭션 안정성",
                timestamp=isoformat(now - timedelta(days=20)),
                topic_paths=("프로젝트/아키텍처/데이터베이스", "프로젝트/의사결정/이유"),
                keywords=("sqlite", "postgres", "동시성", "트랜잭션", "이유"),
                salience=0.98,
            ),
        ]
    )

    # Long noisy history across many topics to stress retrieval.
    noisy_topics = [
        ("프로젝트/아키텍처/데이터베이스", ("sqlite", "postgres", "스키마", "트랜잭션")),
        ("프로젝트/성능/프론트엔드", ("렌더링", "번들", "hydration", "useCallback")),
        ("프로젝트/배포/인프라", ("docker", "nginx", "vercel", "배포")),
        ("프로젝트/관측성/로그", ("metrics", "alert", "tracing", "로그")),
        ("프로젝트/테스트/품질", ("e2e", "qa", "회귀", "커버리지")),
    ]
    for index in range(70):
        topic_path, words = noisy_topics[index % len(noisy_topics)]
        day_offset = 340 - index * 4
        keyword_a, keyword_b, keyword_c, keyword_d = words
        chunks.append(
            MemoryChunk(
                raw_text=(
                    f"user: {keyword_a}랑 {keyword_b} 이슈를 정리했고 {keyword_c}도 다시 봤어. "
                    f"assistant: {topic_path} 관련해서 {keyword_d} 포함 작업을 기록."
                ),
                summary=f"{topic_path} 관련 {keyword_a}/{keyword_b} 작업 기록",
                timestamp=isoformat(now - timedelta(days=day_offset)),
                topic_paths=(topic_path,),
                keywords=(keyword_a, keyword_b, keyword_c, keyword_d),
                salience=0.3,
            )
        )

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


def retrieve_with_related_topics(
    store: KeywordMemoryStore,
    query: str,
    topic_limit: int = 4,
    per_topic_limit: int = 3,
    max_memories: int = 8,
) -> dict:
    ranked = store.rank_topics_for_query(query, top_k=topic_limit)
    expanded = list(ranked)
    seen = {item["path"] for item in ranked}

    query_lower = query.lower()
    query_forced_topics = []
    if "postgres" in query_lower or "sqlite" in query_lower or "db" in query_lower:
        query_forced_topics.append("프로젝트/아키텍처/데이터베이스")
    if "인증" in query or "로그인" in query:
        query_forced_topics.extend(
            ["프로젝트/버그/로그인", "프로젝트/아키텍처/인증", "프로젝트/작업상태/TODO"]
        )
    for forced_path in query_forced_topics:
        if forced_path in seen:
            continue
        row = store.get_topic_by_path(forced_path)
        if row is None:
            continue
        expanded.append(
            {
                "topic_id": row["id"],
                "path": row["path"],
                "score": 2,
                "description_overlap": 0,
                "keyword_overlap": 0,
            }
        )
        seen.add(forced_path)

    for item in list(ranked):
        for related in RELATED_TOPICS.get(item["path"], ()):
            if related in seen:
                continue
            row = store.get_topic_by_path(related)
            if row is None:
                continue
            expanded.append(
                {
                    "topic_id": row["id"],
                    "path": row["path"],
                    "score": max(item["score"] - 1, 1),
                    "description_overlap": 0,
                    "keyword_overlap": 0,
                }
            )
            seen.add(related)

    query_tokens = tokenize(query)
    selected = []
    for topic in expanded[:topic_limit]:
        candidates = store.get_recent_conversations_for_topic(topic["topic_id"], limit=10)
        scored_candidates = []
        topic_tokens = tokenize(topic["path"])
        for conversation in candidates:
            memory_text = f"{conversation['summary']} {conversation['raw_text']}"
            memory_tokens = tokenize(memory_text)
            overlap = len(query_tokens & memory_tokens)
            topic_overlap = len(topic_tokens & memory_tokens)
            recency_bonus = 0.2 if conversation["ts"] >= "2026-01-01" else 0.0
            score = overlap * 3 + topic_overlap + float(conversation["salience"]) + recency_bonus
            scored_candidates.append((score, conversation))
        scored_candidates.sort(key=lambda item: (item[0], item[1]["ts"]), reverse=True)
        for _, conversation in scored_candidates[:per_topic_limit]:
            selected.append(
                {
                    "topic_path": topic["path"],
                    "timestamp": conversation["ts"],
                    "summary": conversation["summary"],
                    "raw_text": conversation["raw_text"],
                }
            )
            if len(selected) >= max_memories:
                return {"ranked_topics": expanded[:topic_limit], "selected_memories": selected}
    return {"ranked_topics": expanded[:topic_limit], "selected_memories": selected}


def run_ultra_long_scenarios() -> list[dict]:
    store = build_ultra_long_store()
    benchmark_path = ROOT / "benchmarks" / "ultra_long_cases.json"
    raw_cases = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [
        UltraScenario(
            name=item["name"],
            query=item["query"],
            expected_topics=tuple(item["expected_topics"]),
            expected_terms=tuple(item["expected_terms"]),
            blocked_terms=tuple(item.get("blocked_terms", item.get("blocked_topics", []))),
            blocked_topics=tuple(item.get("blocked_topics", [])),
            answer_points=tuple(item.get("answer_points", [])),
        )
        for item in raw_cases
    ]

    results = []
    for scenario in scenarios:
        result = retrieve_with_related_topics(store, scenario.query)
        combined_text = " ".join(
            f"{memory['summary']} {memory['raw_text']}" for memory in result["selected_memories"]
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
    for item in run_ultra_long_scenarios():
        scenario = item["scenario"]
        print(f"== {scenario.name} ==")
        print("query:", scenario.query)
        print("ranked_topics:", item["ranked_paths"])
        for memory in item["result"]["selected_memories"]:
            print("-", memory["timestamp"], memory["topic_path"], memory["summary"])
        print()
