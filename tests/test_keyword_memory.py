import unittest
from datetime import datetime, timedelta

from src.keyword_memory import KeywordMemoryStore, MemoryChunk, isoformat, retrieve_memories


def build_store() -> KeywordMemoryStore:
    store = KeywordMemoryStore.create()
    store.seed_topics()
    now = datetime(2026, 5, 11, 20, 0, 0)

    store.save_memory(
        MemoryChunk(
            raw_text="요즘 살 빼려고 저녁 양을 줄이고 있어. 다이어트 계속 하는 중이야.",
            summary="체중 감량 목표와 저녁 식단 조절",
            timestamp=isoformat(now - timedelta(days=90)),
            topic_paths=("건강/체중관리/다이어트",),
            keywords=("다이어트", "식단", "체중감량"),
            salience=0.9,
        )
    )
    store.save_memory(
        MemoryChunk(
            raw_text="밤만 되면 치킨이 너무 먹고 싶고 야식을 참기가 어렵네.",
            summary="야식과 치킨 충동이 반복됨",
            timestamp=isoformat(now - timedelta(days=30)),
            topic_paths=("음식/배달음식/치킨", "행동/식습관/야식"),
            keywords=("치킨", "야식", "식욕"),
            salience=0.8,
        )
    )
    store.save_memory(
        MemoryChunk(
            raw_text="지난번에 치킨 먹고 나니까 죄책감 들고 후회했어.",
            summary="치킨 이후 후회 패턴 확인",
            timestamp=isoformat(now - timedelta(days=7)),
            topic_paths=("음식/배달음식/치킨", "감정/후회/죄책감"),
            keywords=("치킨", "후회", "죄책감"),
            salience=0.7,
        )
    )
    return store


class KeywordMemoryTests(unittest.TestCase):
    def test_save_memory_links_keywords_and_topics(self) -> None:
        store = build_store()
        conversation_count = store.connection.execute(
            "SELECT COUNT(*) AS count FROM conversations"
        ).fetchone()["count"]
        topic_links = store.connection.execute(
            "SELECT COUNT(*) AS count FROM conversation_topics"
        ).fetchone()["count"]
        keyword_links = store.connection.execute(
            "SELECT COUNT(*) AS count FROM conversation_keywords"
        ).fetchone()["count"]

        self.assertEqual(conversation_count, 3)
        self.assertEqual(topic_links, 5)
        self.assertEqual(keyword_links, 9)

    def test_rank_topics_uses_full_query(self) -> None:
        store = build_store()
        ranked = store.rank_topics_for_query("오늘 치킨 먹고 싶은데")

        self.assertTrue(ranked)
        self.assertEqual(ranked[0]["path"], "음식/배달음식/치킨")

    def test_retrieve_memories_scans_recent_first_until_context_is_enough(self) -> None:
        store = build_store()
        result = retrieve_memories(
            store,
            query="오늘 치킨 먹고 싶은데",
            topic_limit=3,
            per_topic_limit=3,
            max_memories=6,
        )

        selected = result["selected_memories"]

        self.assertGreaterEqual(len(selected), 2)
        self.assertGreaterEqual(selected[0]["score"], selected[1]["score"])
        self.assertIn("goal", result["found_constraints"])
        self.assertIn("trigger", result["found_constraints"])

    def test_retrieve_memories_prefers_relevance_over_recency_within_topic(self) -> None:
        store = KeywordMemoryStore.create()
        store.seed_topics()
        now = datetime(2026, 5, 11, 20, 0, 0)

        store.save_memory(
            MemoryChunk(
                raw_text="치킨 먹고 후회했고 야식 때문에 다이어트가 흔들렸어.",
                summary="치킨 야식이 다이어트 목표를 흔든 기록",
                timestamp=isoformat(now - timedelta(days=40)),
                topic_paths=("음식/배달음식/치킨", "건강/체중관리/다이어트"),
                keywords=("치킨", "야식", "다이어트", "후회"),
                salience=0.95,
            )
        )
        store.save_memory(
            MemoryChunk(
                raw_text="오늘 점심에 치킨 신메뉴 사진만 봤어.",
                summary="최신 치킨 잡담",
                timestamp=isoformat(now - timedelta(days=1)),
                topic_paths=("음식/배달음식/치킨",),
                keywords=("치킨",),
                salience=0.1,
            )
        )

        result = retrieve_memories(store, query="오늘 치킨 먹고 싶은데 다이어트 때문에 고민돼", topic_limit=2, per_topic_limit=2)

        self.assertEqual(
            result["selected_memories"][0]["summary"],
            "치킨 야식이 다이어트 목표를 흔든 기록",
        )

    def test_rank_topics_boosts_todo_intent(self) -> None:
        store = KeywordMemoryStore.create()
        store.connection.execute(
            "INSERT INTO topics(path, description) VALUES(?, ?)",
            ("프로젝트/작업상태/TODO", "남은 할일 보류 TODO 미완료"),
        )
        todo_id = store.connection.execute(
            "SELECT id FROM topics WHERE path = ?",
            ("프로젝트/작업상태/TODO",),
        ).fetchone()["id"]
        store.connection.execute(
            "INSERT INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
            ("todo", todo_id),
        )
        store.connection.execute(
            "INSERT INTO topics(path, description) VALUES(?, ?)",
            ("프로젝트/아키텍처/인증", "로그인 인증 세션 구조"),
        )
        auth_id = store.connection.execute(
            "SELECT id FROM topics WHERE path = ?",
            ("프로젝트/아키텍처/인증",),
        ).fetchone()["id"]
        store.connection.execute(
            "INSERT INTO keywords(name, topic_id, weight) VALUES(?, ?, 1)",
            ("인증", auth_id),
        )
        store.connection.commit()

        ranked = store.rank_topics_for_query("인증 쪽 아직 남은 할일 있었나?", top_k=2)

        self.assertEqual(ranked[0]["path"], "프로젝트/작업상태/TODO")

    def test_retrieve_memories_respects_budget_when_context_stays_insufficient(self) -> None:
        store = build_store()
        result = retrieve_memories(
            store,
            query="그냥 메뉴 추천해줘",
            topic_limit=3,
            per_topic_limit=1,
            max_memories=1,
        )

        self.assertLessEqual(len(result["selected_memories"]), 1)


if __name__ == "__main__":
    unittest.main()
