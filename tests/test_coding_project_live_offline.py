import unittest
from datetime import datetime, timedelta

from scripts.coding_project_live_test import (
    create_coding_store,
    retrieve_coding_memories,
    save_coding_memory,
)
from src.keyword_memory import isoformat


class FakeCodingClient:
    def create_json_response(self, instructions: str, input_text: str):
        if "convert an old coding-project conversation block" in instructions.lower():
            block = input_text.split("Conversation block:\n", 1)[-1]
            if "세션 쿠키 기반" in block:
                return {
                    "summary": "로그인 인증은 JWT 대신 세션 쿠키로 가기로 함",
                    "topic_paths": ["프로젝트/아키텍처/인증", "프로젝트/의사결정/이유"],
                    "keywords": ["로그인", "인증", "세션", "쿠키"],
                    "salience": 0.9,
                }
            if "sqlite로 빠르게 가고" in block:
                return {
                    "summary": "개발 초기엔 sqlite, 운영 전환 시 postgres로 이동",
                    "topic_paths": ["프로젝트/아키텍처/데이터베이스", "프로젝트/의사결정/이유"],
                    "keywords": ["sqlite", "postgres", "마이그레이션"],
                    "salience": 0.85,
                }
            if "401이 뜬다" in block:
                return {
                    "summary": "새로고침 후 401이 뜨는 로그인 버그 기록",
                    "topic_paths": ["프로젝트/버그/로그인", "프로젝트/아키텍처/인증"],
                    "keywords": ["로그인버그", "401", "리다이렉트", "세션만료"],
                    "salience": 0.95,
                }
            if "useMemo" in block:
                return {
                    "summary": "과한 메모이제이션 리팩터링은 피하기로 함",
                    "topic_paths": ["프로젝트/선호/코드스타일"],
                    "keywords": ["useMemo", "useCallback", "리팩터링", "선호"],
                    "salience": 0.88,
                }
            if "csrf 정리와 테스트 추가" in block:
                return {
                    "summary": "csrf 정리와 인증 테스트는 후속 TODO",
                    "topic_paths": ["프로젝트/작업상태/TODO", "프로젝트/아키텍처/인증"],
                    "keywords": ["csrf", "테스트", "todo", "보류"],
                    "salience": 0.8,
                }
            if "동시성 쪽이 불안" in block:
                return {
                    "summary": "postgres 전환 이유는 동시성과 트랜잭션 안정성",
                    "topic_paths": ["프로젝트/아키텍처/데이터베이스", "프로젝트/의사결정/이유"],
                    "keywords": ["sqlite", "postgres", "동시성", "트랜잭션"],
                    "salience": 0.93,
                }
            return {
                "summary": "쿠키 만료 후 리다이렉트 UX 이슈가 남아 있음",
                "topic_paths": ["프로젝트/버그/로그인", "프로젝트/작업상태/TODO"],
                "keywords": ["쿠키", "리다이렉트", "todo", "미완료"],
                "salience": 0.91,
            }

        if "select which coding-project memory topics" in instructions.lower():
            if "sqlite 말고 postgres" in input_text:
                return {
                    "topics": [
                        {"topic_path": "프로젝트/아키텍처/데이터베이스", "reason": "DB 결정 질문", "score": 10}
                    ]
                }
            if "리팩터링 방식" in input_text:
                return {
                    "topics": [
                        {"topic_path": "프로젝트/선호/코드스타일", "reason": "선호 회상", "score": 10}
                    ]
                }
            if "남은 할일" in input_text:
                return {
                    "topics": [
                        {"topic_path": "프로젝트/작업상태/TODO", "reason": "미완료 작업 회상", "score": 10}
                    ]
                }
            return {
                "topics": [
                    {"topic_path": "프로젝트/버그/로그인", "reason": "인증 버그 회상", "score": 10}
                ]
            }

        if "decide whether the memory search has enough personal context" in instructions.lower():
            if "sqlite 말고 postgres" in input_text:
                enough = "동시성" in input_text and "sqlite" in input_text
            elif "리팩터링 방식" in input_text:
                enough = "useMemo" in input_text
            elif "남은 할일" in input_text:
                enough = "csrf" in input_text or "미완료" in input_text
            else:
                enough = "401" in input_text and "쿠키" in input_text
            return {
                "enough": enough,
                "reason": "충분" if enough else "아직 부족",
                "missing_info": [] if enough else ["추가 맥락"],
            }

        raise AssertionError("Unexpected prompt")


class CodingProjectLiveOfflineTests(unittest.TestCase):
    def test_coding_live_flow_offline(self) -> None:
        store = create_coding_store()
        client = FakeCodingClient()
        now = datetime(2026, 5, 11, 22, 30, 0)
        transcript_blocks = [
            (
                "user: 로그인 구현은 일단 세션 쿠키 기반으로 가자. JWT는 지금 단계에선 과하다.\nassistant: 인증 구조는 서버 세션과 쿠키로 유지하기로 결정.",
                isoformat(now - timedelta(days=120)),
            ),
            (
                "user: 처음엔 sqlite로 빠르게 가고, 배포 전엔 postgres로 옮기자.\nassistant: 개발 속도 때문에 sqlite를 먼저 쓰고 이후 postgres로 마이그레이션.",
                isoformat(now - timedelta(days=110)),
            ),
            (
                "user: 로그인 후 새로고침하면 가끔 401이 뜬다.\nassistant: 세션 만료 처리와 리다이렉트 흐름에 버그가 있어 보인다.",
                isoformat(now - timedelta(days=75)),
            ),
            (
                "user: useMemo, useCallback 남발하는 리팩터링은 싫어. 읽기 더 어려워져.\nassistant: 과한 메모이제이션 스타일은 피하고 단순한 구조를 선호.",
                isoformat(now - timedelta(days=60)),
            ),
            (
                "user: 로그인 버그 고치고 나면 csrf 정리와 테스트 추가는 TODO로 남겨두자.\nassistant: csrf 정리와 인증 테스트 확장은 후속 작업으로 보류.",
                isoformat(now - timedelta(days=45)),
            ),
            (
                "user: sqlite는 동시성 쪽이 불안해서 결국 postgres로 가야 할 것 같아.\nassistant: 운영 환경 동시성과 트랜잭션 안정성 때문에 postgres 전환 근거를 확인.",
                isoformat(now - timedelta(days=20)),
            ),
            (
                "user: 로그인 쪽은 고쳤는데 쿠키 만료 후 리다이렉트가 아직 어색해.\nassistant: 로그인 버그는 완전히 끝난 게 아니라 쿠키 만료 UX가 남아 있음.",
                isoformat(now - timedelta(days=10)),
            ),
        ]

        for transcript, timestamp in transcript_blocks:
            save_coding_memory(store, client, transcript, timestamp)

        scenarios = [
            "그 인증 버그 다시 보자",
            "우리가 왜 sqlite 말고 postgres로 가기로 했지?",
            "지난번에 싫다고 한 리팩터링 방식 뭐였지?",
            "인증 쪽 아직 남은 할일 있었나?",
        ]

        for query in scenarios:
            chosen_topics, collected, traces = retrieve_coding_memories(store, client, query)
            self.assertTrue(chosen_topics, msg=query)
            self.assertTrue(collected, msg=query)
            self.assertTrue(any(item["enough"] for item in traces), msg=query)


if __name__ == "__main__":
    unittest.main()
