from __future__ import annotations

import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.keyword_memory import (
    KeywordMemoryStore,
    MemoryChunk,
    RELATED_TOPICS,
    TOPIC_SEEDS,
    isoformat,
    tokenize,
)


DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
API_URL = "https://api.openai.com/v1/responses"


@dataclass
class TopicChoice:
    topic_path: str
    reason: str
    score: int


@dataclass
class ContinueDecision:
    enough: bool
    reason: str
    missing_info: list[str]


class OpenAIResponsesClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def create_json_response(self, instructions: str, input_text: str) -> dict[str, Any]:
        json_input = f"Return json.\n\n{input_text}"
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": json_input,
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling OpenAI API: {exc}") from exc

        data = json.loads(raw)
        output_text = self._extract_output_text(data)
        if not output_text:
            raise RuntimeError(f"Response did not contain output text: {raw}")
        return json.loads(output_text)

    def create_text_response(self, instructions: str, input_text: str) -> str:
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling OpenAI API: {exc}") from exc

        data = json.loads(raw)
        output_text = self._extract_output_text(data)
        if not output_text:
            raise RuntimeError(f"Response did not contain output text: {raw}")
        return output_text.strip()

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        texts: list[str] = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        return "".join(texts).strip()


def topic_catalog_text() -> str:
    return "\n".join(
        f"- {seed.path}: {seed.description} | keywords={', '.join(seed.keywords)}"
        for seed in TOPIC_SEEDS
    )


def normalize_topic_paths(candidate_paths: Sequence[str], raw_text: str) -> tuple[str, ...]:
    allowed_paths = [seed.path for seed in TOPIC_SEEDS]
    normalized: list[str] = []

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
    fallback: list[str] = []
    for seed in TOPIC_SEEDS:
        overlap = len(text_tokens & tokenize(seed.description + " " + " ".join(seed.keywords)))
        if overlap > 0:
            fallback.append(seed.path)
    return tuple(fallback[:3])


def normalize_keywords(candidate_keywords: Sequence[str], raw_text: str) -> tuple[str, ...]:
    cleaned = [str(keyword).strip() for keyword in candidate_keywords if str(keyword).strip()]
    if cleaned:
        return tuple(dict.fromkeys(cleaned[:8]))

    text_tokens = tokenize(raw_text)
    fallback: list[str] = []
    for seed in TOPIC_SEEDS:
        for keyword in seed.keywords:
            if keyword.lower() in text_tokens:
                fallback.append(keyword)
    return tuple(dict.fromkeys(fallback[:8]))


def extract_memory_chunk(
    client: OpenAIResponsesClient,
    transcript_block: str,
    timestamp: str,
) -> MemoryChunk:
    instructions = textwrap.dedent(
        """
        You convert an old conversation block into structured memory.
        Return strict json with keys:
        - summary: short Korean summary
        - topic_paths: array of exact topic paths chosen only from the provided catalog
        - keywords: array of 3 to 8 Korean keywords grounded in the text
        - salience: number from 0 to 1
        Do not invent topics outside the catalog.
        """
    ).strip()
    input_text = textwrap.dedent(
        f"""
        Topic catalog:
        {topic_catalog_text()}

        Conversation block:
        {transcript_block}
        """
    ).strip()
    data = client.create_json_response(instructions, input_text)
    topic_paths = normalize_topic_paths(data.get("topic_paths", []), transcript_block)
    keywords = normalize_keywords(data.get("keywords", []), transcript_block)
    if not topic_paths:
        raise RuntimeError(f"Model did not return usable topic paths: {json.dumps(data, ensure_ascii=False)}")
    if not keywords:
        raise RuntimeError(f"Model did not return usable keywords: {json.dumps(data, ensure_ascii=False)}")
    return MemoryChunk(
        raw_text=transcript_block,
        summary=str(data["summary"]).strip(),
        timestamp=timestamp,
        topic_paths=topic_paths,
        keywords=keywords,
        salience=float(data.get("salience", 0.5)),
    )


def choose_topics(
    client: OpenAIResponsesClient,
    query: str,
    max_topics: int = 3,
) -> list[TopicChoice]:
    instructions = textwrap.dedent(
        """
        You select which memory topics should be explored for a new user query.
        Return strict json with:
        - topics: array of objects {topic_path, reason, score}
        Choose only from the catalog.
        Use the full query meaning, not keyword extraction.
        """
    ).strip()
    input_text = textwrap.dedent(
        f"""
        Topic catalog:
        {topic_catalog_text()}

        User query:
        {query}

        Select up to {max_topics} topics.
        """
    ).strip()
    data = client.create_json_response(instructions, input_text)
    topics: list[TopicChoice] = []
    seen_paths: set[str] = set()
    for item in data.get("topics", []):
        normalized_paths = normalize_topic_paths([item.get("topic_path", "")], query)
        if not normalized_paths:
            continue
        normalized_path = normalized_paths[0]
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        topics.append(
            TopicChoice(
                topic_path=normalized_path,
                reason=str(item.get("reason", "관련 토픽")),
                score=int(item.get("score", 1)),
            )
        )
        if len(topics) >= max_topics:
            break
    return topics


def decide_continue(
    client: OpenAIResponsesClient,
    query: str,
    collected_memories: Sequence[dict[str, Any]],
) -> ContinueDecision:
    instructions = textwrap.dedent(
        """
        You decide whether the memory search has enough personal context.
        Return strict json with:
        - enough: boolean
        - reason: short Korean explanation
        - missing_info: array of short Korean strings
        Answer enough=true when the collected memories already contain useful personal goals,
        constraints, habits, or emotional patterns that help answer the current query.
        """
    ).strip()
    rendered_memories = "\n\n".join(
        [
            f"[{idx + 1}] {memory['timestamp']} {memory['topic_path']}\n"
            f"summary={memory['summary']}\n"
            f"text={memory['raw_text']}"
            for idx, memory in enumerate(collected_memories)
        ]
    )
    input_text = textwrap.dedent(
        f"""
        User query:
        {query}

        Collected memories:
        {rendered_memories or '(none)'}
        """
    ).strip()
    data = client.create_json_response(instructions, input_text)
    return ContinueDecision(
        enough=bool(data["enough"]),
        reason=data["reason"],
        missing_info=list(data["missing_info"]),
    )


def answer_query(
    client: OpenAIResponsesClient,
    query: str,
    collected_memories: Sequence[dict[str, Any]],
) -> str:
    instructions = textwrap.dedent(
        """
        Answer the user's latest message in Korean.
        Use the referenced personal memory only when relevant.
        Mention the remembered context naturally, not mechanically.
        """
    ).strip()
    rendered_memories = "\n\n".join(
        [
            f"[{idx + 1}] {memory['timestamp']} {memory['topic_path']}\n"
            f"summary={memory['summary']}\n"
            f"text={memory['raw_text']}"
            for idx, memory in enumerate(collected_memories)
        ]
    )
    input_text = textwrap.dedent(
        f"""
        Current user query:
        {query}

        Retrieved memory:
        {rendered_memories or '(none)'}
        """
    ).strip()
    return client.create_text_response(instructions, input_text)


def save_llm_memory(
    store: KeywordMemoryStore,
    client: OpenAIResponsesClient,
    transcript_block: str,
    timestamp: str,
) -> MemoryChunk:
    chunk = extract_memory_chunk(client, transcript_block, timestamp)
    known_keywords = {
        row["name"]
        for row in store.connection.execute("SELECT name FROM keywords").fetchall()
    }
    for keyword in chunk.keywords:
        if keyword in known_keywords:
            continue
        first_topic = chunk.topic_paths[0]
        topic_id = store.connection.execute(
            "SELECT id FROM topics WHERE path = ?",
            (first_topic,),
        ).fetchone()["id"]
        store.connection.execute(
            "INSERT OR IGNORE INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
            (keyword, topic_id),
        )
    store.connection.commit()
    store.save_memory(chunk)
    return chunk


def retrieve_with_llm(
    store: KeywordMemoryStore,
    client: OpenAIResponsesClient,
    query: str,
    per_topic_limit: int = 3,
    max_memories: int = 6,
) -> tuple[list[TopicChoice], list[dict[str, Any]], list[dict[str, Any]]]:
    chosen_topics = choose_topics(client, query)
    expanded_topics: list[TopicChoice] = []
    seen_topic_paths: set[str] = set()
    for topic in chosen_topics:
        if topic.topic_path not in seen_topic_paths:
            expanded_topics.append(topic)
            seen_topic_paths.add(topic.topic_path)
        for related_path in RELATED_TOPICS.get(topic.topic_path, ()):
            if related_path in seen_topic_paths:
                continue
            expanded_topics.append(
                TopicChoice(
                    topic_path=related_path,
                    reason=f"{topic.topic_path}에서 연관 토픽 확장",
                    score=max(topic.score - 1, 1),
                )
            )
            seen_topic_paths.add(related_path)
    traces: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []

    for topic in expanded_topics:
        topic_row = store.get_topic_by_path(topic.topic_path)
        if topic_row is None:
            traces.append(
                {
                    "topic_path": topic.topic_path,
                    "reason": topic.reason,
                    "score": topic.score,
                    "status": "missing_topic",
                }
            )
            continue
        conversations = store.get_recent_conversations_for_topic(
            topic_row["id"], limit=per_topic_limit
        )
        for conversation in conversations:
            memory = {
                "topic_path": topic.topic_path,
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
                    "topic_path": topic.topic_path,
                    "reason": topic.reason,
                    "score": topic.score,
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


def run_demo() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAIResponsesClient(api_key=api_key)
    store = KeywordMemoryStore.create()
    store.seed_topics()

    now = datetime(2026, 5, 11, 21, 0, 0)
    transcript_blocks = [
        (
            "user: 요즘 살을 빼고 싶어서 저녁은 줄이고 있어.\n"
            "assistant: 목표는 체중 감량이고 저녁 식단을 조절 중이군요.",
            isoformat(now - timedelta(days=90)),
        ),
        (
            "user: 밤만 되면 치킨이 너무 먹고 싶어. 야식 참기가 힘들다.\n"
            "assistant: 야식 충동이 반복되고 있네요.",
            isoformat(now - timedelta(days=30)),
        ),
        (
            "user: 지난주에 치킨 시켜 먹고 너무 후회했어.\n"
            "assistant: 먹고 난 뒤 죄책감이 남았군요.",
            isoformat(now - timedelta(days=7)),
        ),
    ]

    print("== Step 1. Save evicted conversations with LLM extraction ==")
    for transcript, timestamp in transcript_blocks:
        chunk = save_llm_memory(store, client, transcript, timestamp)
        print(json.dumps(asdict(chunk), ensure_ascii=False, indent=2))

    query = "오늘 치킨 먹고 싶은데"
    print("\n== Step 2. Choose topics from the full query ==")
    chosen_topics, collected, traces = retrieve_with_llm(store, client, query)
    print(json.dumps([asdict(topic) for topic in chosen_topics], ensure_ascii=False, indent=2))

    print("\n== Step 3. Sequential memory traversal ==")
    print(json.dumps(traces, ensure_ascii=False, indent=2))

    print("\n== Step 4. Final answer using retrieved memory ==")
    final_answer = answer_query(client, query, collected)
    print(final_answer)


if __name__ == "__main__":
    run_demo()
