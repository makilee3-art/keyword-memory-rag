from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.live_chat_test import (
    OpenAIResponsesClient,
    answer_query,
    retrieve_with_llm,
    save_llm_memory,
)
from src.keyword_memory import KeywordMemoryStore


def build_store(db_path: Path) -> KeywordMemoryStore:
    store = KeywordMemoryStore.create(str(db_path))
    store.seed_topics()
    return store


def run_chat() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    client = OpenAIResponsesClient(api_key=api_key, model=model)
    db_path = Path(__file__).resolve().parent / "session.db"
    store = build_store(db_path)

    print("Long-memory ChatGPT API playground")
    print("Type /exit to quit.")

    while True:
        user_text = input("\nYou: ").strip()
        if not user_text:
            continue
        if user_text in {"/exit", "/quit"}:
            break

        chosen_topics, collected, _traces = retrieve_with_llm(store, client, user_text)
        assistant_text = answer_query(client, user_text, collected)
        print("\nAssistant:\n" + assistant_text)

        transcript_block = (
            f"user: {user_text}\n"
            f"assistant: {assistant_text}\n"
        )
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        save_llm_memory(store, client, transcript_block, timestamp)


if __name__ == "__main__":
    run_chat()
