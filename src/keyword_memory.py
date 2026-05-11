from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[0-9A-Za-z가-힣]+", normalize_text(text)))


def recency_score(timestamp: str, now: datetime | None = None) -> float:
    now = now or datetime.now()
    dt = datetime.fromisoformat(timestamp)
    age_days = max((now - dt).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.7
    if age_days <= 90:
        return 0.4
    return 0.2


def detect_query_intent(query: str) -> dict[str, float]:
    normalized = normalize_text(query)
    boosts: dict[str, float] = {}
    if any(token in normalized for token in ("왜", "이유", "근거", "트레이드오프", "왜 바꾸")):
        boosts["프로젝트/의사결정/이유"] = 3.0
    if any(token in normalized for token in ("남은", "할일", "todo", "보류", "미완료", "안 끝", "아직", "후속")):
        boosts["프로젝트/작업상태/TODO"] = 3.0
    if any(token in normalized for token in ("버그", "에러", "오류", "실패", "401")):
        boosts["프로젝트/버그/로그인"] = 2.5
    if any(token in normalized for token in ("인증", "로그인", "세션", "쿠키")):
        boosts["프로젝트/아키텍처/인증"] = max(boosts.get("프로젝트/아키텍처/인증", 0.0), 1.5)
    if any(token in normalized for token in ("postgres", "sqlite", "db", "데이터베이스")):
        boosts["프로젝트/아키텍처/데이터베이스"] = 2.5
    return boosts


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  summary TEXT DEFAULT '',
  salience REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keywords (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  topic_id INTEGER NOT NULL,
  weight REAL DEFAULT 1,
  FOREIGN KEY (topic_id) REFERENCES topics (id)
);

CREATE TABLE IF NOT EXISTS conversation_topics (
  conversation_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  strength REAL DEFAULT 1,
  PRIMARY KEY (conversation_id, topic_id),
  FOREIGN KEY (conversation_id) REFERENCES conversations (id),
  FOREIGN KEY (topic_id) REFERENCES topics (id)
);

CREATE TABLE IF NOT EXISTS conversation_keywords (
  conversation_id INTEGER NOT NULL,
  keyword_id INTEGER NOT NULL,
  strength REAL DEFAULT 1,
  PRIMARY KEY (conversation_id, keyword_id),
  FOREIGN KEY (conversation_id) REFERENCES conversations (id),
  FOREIGN KEY (keyword_id) REFERENCES keywords (id)
);
"""


@dataclass(frozen=True)
class TopicSeed:
    path: str
    description: str
    keywords: Sequence[str]


@dataclass(frozen=True)
class MemoryChunk:
    raw_text: str
    summary: str
    timestamp: str
    topic_paths: Sequence[str]
    keywords: Sequence[str]
    salience: float = 0.0


TOPIC_SEEDS: tuple[TopicSeed, ...] = (
    TopicSeed(
        path="건강/체중관리/다이어트",
        description="체중 감량 식단 칼로리 목표 관리",
        keywords=("다이어트", "체중감량", "감량", "식단", "칼로리", "체중관리"),
    ),
    TopicSeed(
        path="음식/배달음식/치킨",
        description="치킨 배달 음식 후라이드 양념 메뉴 선택",
        keywords=("치킨", "후라이드", "양념치킨", "배달음식", "닭", "치킨메뉴"),
    ),
    TopicSeed(
        path="행동/식습관/야식",
        description="밤 야식 폭식 참기 어려움 식욕 충동",
        keywords=("야식", "밤에먹기", "폭식", "식욕", "먹고싶다", "참기힘듦"),
    ),
    TopicSeed(
        path="감정/후회/죄책감",
        description="먹은 뒤 후회 죄책감 의지 흔들림",
        keywords=("후회", "죄책감", "의지", "흔들림"),
    ),
)

RELATED_TOPICS: dict[str, tuple[str, ...]] = {
    "음식/배달음식/치킨": (
        "행동/식습관/야식",
        "건강/체중관리/다이어트",
        "감정/후회/죄책감",
    ),
    "행동/식습관/야식": (
        "건강/체중관리/다이어트",
        "감정/후회/죄책감",
    ),
}


class KeywordMemoryStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def create(cls, path: str = ":memory:") -> "KeywordMemoryStore":
        connection = sqlite3.connect(path)
        store = cls(connection)
        store.initialize()
        return store

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def seed_topics(self, seeds: Iterable[TopicSeed] = TOPIC_SEEDS) -> None:
        for seed in seeds:
            self.connection.execute(
                "INSERT OR IGNORE INTO topics(path, description) VALUES(?, ?)",
                (seed.path, seed.description),
            )
            topic_id = self.connection.execute(
                "SELECT id FROM topics WHERE path = ?",
                (seed.path,),
            ).fetchone()["id"]
            for keyword in seed.keywords:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO keywords(name, topic_id, weight)
                    VALUES(?, ?, 1)
                    """,
                    (keyword, topic_id),
                )
        self.connection.commit()

    def save_memory(self, chunk: MemoryChunk) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO conversations(ts, raw_text, summary, salience)
            VALUES(?, ?, ?, ?)
            """,
            (chunk.timestamp, chunk.raw_text, chunk.summary, chunk.salience),
        )
        conversation_id = int(cursor.lastrowid)
        for topic_path in chunk.topic_paths:
            topic_row = self.connection.execute(
                "SELECT id FROM topics WHERE path = ?",
                (topic_path,),
            ).fetchone()
            if topic_row is None:
                raise ValueError(f"Unknown topic path: {topic_path}")
            self.connection.execute(
                """
                INSERT OR REPLACE INTO conversation_topics(conversation_id, topic_id, strength)
                VALUES(?, ?, 1)
                """,
                (conversation_id, topic_row["id"]),
            )
        for keyword in chunk.keywords:
            keyword_row = self.connection.execute(
                "SELECT id FROM keywords WHERE name = ?",
                (keyword,),
            ).fetchone()
            if keyword_row is None:
                raise ValueError(f"Unknown keyword: {keyword}")
            self.connection.execute(
                """
                INSERT OR REPLACE INTO conversation_keywords(conversation_id, keyword_id, strength)
                VALUES(?, ?, 1)
                """,
                (conversation_id, keyword_row["id"]),
            )
        self.connection.commit()
        return conversation_id

    def rank_topics_for_query(self, query: str, top_k: int = 3) -> list[dict]:
        query_tokens = tokenize(query)
        intent_boosts = detect_query_intent(query)
        rows = self.connection.execute(
            """
            SELECT
              t.id,
              t.path,
              t.description,
              GROUP_CONCAT(k.name, ' ') AS keywords
            FROM topics t
            LEFT JOIN keywords k ON k.topic_id = t.id
            GROUP BY t.id, t.path, t.description
            """
        ).fetchall()

        ranked: list[dict] = []
        for row in rows:
            topic_tokens = tokenize(row["description"] or "")
            keyword_tokens = tokenize(row["keywords"] or "")
            description_overlap = len(query_tokens & topic_tokens)
            keyword_overlap = len(query_tokens & keyword_tokens)
            score = (
                description_overlap * 2
                + keyword_overlap
                + intent_boosts.get(row["path"], 0.0)
            )
            if score <= 0:
                continue
            ranked.append(
                {
                    "topic_id": row["id"],
                    "path": row["path"],
                    "score": score,
                    "description_overlap": description_overlap,
                    "keyword_overlap": keyword_overlap,
                }
            )
        ranked.sort(key=lambda item: (-item["score"], item["path"]))
        return ranked[:top_k]

    def get_recent_conversations_for_topic(self, topic_id: int, limit: int = 3) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT c.id, c.ts, c.raw_text, c.summary, c.salience
                FROM conversations c
                JOIN conversation_topics ct ON ct.conversation_id = c.id
                WHERE ct.topic_id = ?
                ORDER BY c.ts DESC, c.id DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        )

    def get_all_conversations_for_topic(self, topic_id: int, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT c.id, c.ts, c.raw_text, c.summary, c.salience
                FROM conversations c
                JOIN conversation_topics ct ON ct.conversation_id = c.id
                WHERE ct.topic_id = ?
                ORDER BY c.ts DESC, c.id DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        )

    def get_keywords_for_conversation(self, conversation_id: int) -> set[str]:
        rows = self.connection.execute(
            """
            SELECT k.name
            FROM keywords k
            JOIN conversation_keywords ck ON ck.keyword_id = k.id
            WHERE ck.conversation_id = ?
            """,
            (conversation_id,),
        ).fetchall()
        return {row["name"] for row in rows}

    def get_topic_by_path(self, path: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT id, path, description FROM topics WHERE path = ?",
            (path,),
        ).fetchone()


def should_continue(
    found_constraints: set[str],
    max_memories: int,
    seen_count: int,
) -> bool:
    if seen_count >= max_memories:
        return False
    required = {"goal", "trigger"}
    return not required.issubset(found_constraints)


def inspect_memory(memory_text: str) -> set[str]:
    tokens = tokenize(memory_text)
    signals: set[str] = set()
    if {"다이어트", "체중감량", "식단", "저녁"} & tokens:
        signals.add("goal")
    if {"치킨", "야식", "식욕", "폭식"} & tokens:
        signals.add("trigger")
    if {"후회", "죄책감"} & tokens:
        signals.add("risk")
    return signals


def memory_score(
    query: str,
    topic_path: str,
    conversation: sqlite3.Row,
    conversation_keywords: set[str],
    now: datetime | None = None,
) -> float:
    query_tokens = tokenize(query)
    text_tokens = tokenize(f"{conversation['summary']} {conversation['raw_text']}")
    keyword_tokens = {normalize_text(keyword) for keyword in conversation_keywords}
    topic_tokens = tokenize(topic_path)

    text_overlap = len(query_tokens & text_tokens)
    keyword_overlap = len(query_tokens & keyword_tokens)
    topic_overlap = len(query_tokens & topic_tokens)
    score = (
        3.0 * text_overlap
        + 2.0 * keyword_overlap
        + 1.5 * topic_overlap
        + 1.0 * float(conversation["salience"])
        + 0.8 * recency_score(conversation["ts"], now=now)
    )
    return score


def similarity_penalty(
    conversation: sqlite3.Row,
    topic_path: str,
    already_selected: Sequence[dict],
) -> float:
    candidate_tokens = tokenize(f"{conversation['summary']} {conversation['raw_text']}")
    penalty = 0.0
    for selected in already_selected:
        selected_tokens = tokenize(f"{selected['summary']} {selected['raw_text']}")
        if not candidate_tokens or not selected_tokens:
            continue
        overlap = len(candidate_tokens & selected_tokens)
        union = len(candidate_tokens | selected_tokens)
        jaccard = overlap / union if union else 0.0
        if selected["topic_path"] == topic_path:
            penalty = max(penalty, jaccard)
    return penalty


def topic_diversity_penalty(
    topic_path: str,
    already_selected: Sequence[dict],
) -> float:
    same_topic_count = sum(1 for selected in already_selected if selected["topic_path"] == topic_path)
    if same_topic_count <= 0:
        return 0.0
    return min(0.4 * same_topic_count, 1.2)


def retrieve_memories(
    store: KeywordMemoryStore,
    query: str,
    topic_limit: int = 3,
    per_topic_limit: int = 3,
    max_memories: int = 6,
) -> dict:
    now = datetime.now()
    ranked_topics = store.rank_topics_for_query(query, top_k=topic_limit)
    expanded_topics: list[dict] = list(ranked_topics)
    seen_topic_paths = {topic["path"] for topic in ranked_topics}
    for topic in ranked_topics:
        for related_path in RELATED_TOPICS.get(topic["path"], ()):
            if related_path in seen_topic_paths:
                continue
            related_row = store.get_topic_by_path(related_path)
            if related_row is None:
                continue
            expanded_topics.append(
                {
                    "topic_id": related_row["id"],
                    "path": related_row["path"],
                    "score": max(topic["score"] - 1, 1),
                    "description_overlap": 0,
                    "keyword_overlap": 0,
                }
            )
            seen_topic_paths.add(related_path)

    selected: list[dict] = []
    found_constraints: set[str] = set()
    seen_count = 0

    for topic in expanded_topics[:topic_limit]:
        candidates = store.get_all_conversations_for_topic(topic["topic_id"], limit=20)
        scored_candidates: list[tuple[float, sqlite3.Row]] = []
        for conversation in candidates:
            keywords = store.get_keywords_for_conversation(conversation["id"])
            base_score = memory_score(
                query=query,
                topic_path=topic["path"],
                conversation=conversation,
                conversation_keywords=keywords,
                now=now,
            )
            penalty = similarity_penalty(conversation, topic["path"], selected)
            diversity = topic_diversity_penalty(topic["path"], selected)
            final_score = base_score - (penalty * 1.5) - diversity
            scored_candidates.append((final_score, conversation))
        scored_candidates.sort(key=lambda item: (item[0], item[1]["ts"]), reverse=True)
        for score, conversation in scored_candidates[:per_topic_limit]:
            selected.append(
                {
                    "topic_path": topic["path"],
                    "conversation_id": conversation["id"],
                    "timestamp": conversation["ts"],
                    "summary": conversation["summary"],
                    "raw_text": conversation["raw_text"],
                    "score": round(score, 3),
                }
            )
            found_constraints |= inspect_memory(
                f"{conversation['summary']} {conversation['raw_text']}"
            )
            seen_count += 1
            if not should_continue(found_constraints, max_memories, seen_count):
                return {
                    "ranked_topics": expanded_topics[:topic_limit],
                    "selected_memories": selected,
                    "found_constraints": sorted(found_constraints),
                }
    return {
        "ranked_topics": expanded_topics[:topic_limit],
        "selected_memories": selected,
        "found_constraints": sorted(found_constraints),
    }


def isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()
