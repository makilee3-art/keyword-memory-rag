import json
import unittest
from datetime import datetime, timedelta

from src.keyword_memory import KeywordMemoryStore, isoformat
from scripts.live_chat_test import retrieve_with_llm, save_llm_memory


class FakeClient:
    def __init__(self) -> None:
        self.memory_calls = 0

    def create_json_response(self, instructions: str, input_text: str):
        if "convert an old conversation block" in instructions.lower():
            self.memory_calls += 1
            if "저녁은 줄이고 있어" in input_text:
                return {
                    "summary": "체중 감량 목표와 저녁 식단 조절",
                    "topic_paths": ["건강/체중관리/다이어트"],
                    "keywords": ["다이어트", "식단", "체중감량"],
                    "salience": 0.9,
                }
            if "야식 참기가 힘들다" in input_text:
                return {
                    "summary": "야식과 치킨 충동이 반복됨",
                    "topic_paths": ["음식/배달음식/치킨", "행동/식습관/야식"],
                    "keywords": ["치킨", "야식", "식욕"],
                    "salience": 0.8,
                }
            return {
                "summary": "치킨 이후 후회 패턴 확인",
                "topic_paths": ["음식/배달음식/치킨", "감정/후회/죄책감"],
                "keywords": ["치킨", "후회", "죄책감"],
                "salience": 0.7,
            }
        if "select which memory topics" in instructions.lower():
            return {
                "topics": [
                    {"topic_path": "음식/배달음식/치킨", "reason": "직접 관련", "score": 10},
                    {"topic_path": "건강/체중관리/다이어트", "reason": "먹는 선택과 목표 충돌", "score": 8},
                ]
            }
        if "decide whether the memory search has enough personal context" in instructions.lower():
            enough = "저녁 식단 조절" in input_text and "야식과 치킨 충동" in input_text
            return {
                "enough": enough,
                "reason": "목표와 충동 정보가 확보됨" if enough else "아직 목표 정보가 없음",
                "missing_info": [] if enough else ["현재 체중 감량 목표"],
            }
        raise AssertionError("Unexpected prompt")


class LiveChatOfflineTests(unittest.TestCase):
    def test_live_flow_offline(self) -> None:
        store = KeywordMemoryStore.create()
        store.seed_topics()
        client = FakeClient()
        now = datetime(2026, 5, 11, 21, 0, 0)

        transcript_blocks = [
            (
                "user: 요즘 살을 빼고 싶어서 저녁은 줄이고 있어.\nassistant: 목표는 체중 감량이고 저녁 식단을 조절 중이군요.",
                isoformat(now - timedelta(days=90)),
            ),
            (
                "user: 밤만 되면 치킨이 너무 먹고 싶어. 야식 참기가 힘들다.\nassistant: 야식 충동이 반복되고 있네요.",
                isoformat(now - timedelta(days=30)),
            ),
            (
                "user: 지난주에 치킨 시켜 먹고 너무 후회했어.\nassistant: 먹고 난 뒤 죄책감이 남았군요.",
                isoformat(now - timedelta(days=7)),
            ),
        ]

        for transcript, timestamp in transcript_blocks:
            save_llm_memory(store, client, transcript, timestamp)

        chosen_topics, collected, traces = retrieve_with_llm(
            store,
            client,
            "오늘 치킨 먹고 싶은데",
        )

        self.assertEqual(client.memory_calls, 3)
        self.assertGreaterEqual(len(chosen_topics), 2)
        self.assertEqual(chosen_topics[0].topic_path, "음식/배달음식/치킨")
        self.assertGreaterEqual(len(collected), 2)
        self.assertTrue(any(item["enough"] for item in traces))


if __name__ == "__main__":
    unittest.main()
