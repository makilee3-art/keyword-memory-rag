import unittest

from scripts.answer_benchmark_live import evaluate_live_answers


class FakeAnswerClient:
    def create_json_response(self, instructions: str, input_text: str):
        if "grading a korean answer for a memory-retrieval benchmark" in instructions.lower():
            if "Candidate answer:\n로그인 버그 쪽으로는 401" in input_text:
                return {
                    "point_coverage": 0.6,
                    "relevance": 0.8,
                    "groundedness": 0.9,
                    "verdict": "핵심은 맞지만 남은 할일 반영이 약함",
                }
            return {
                "point_coverage": 0.9,
                "relevance": 0.9,
                "groundedness": 0.95,
                "verdict": "핵심 포인트를 잘 반영함",
            }
        raise AssertionError("Unexpected JSON prompt")

    def create_text_response(self, instructions: str, input_text: str) -> str:
        if "지난번에 싫다고 한 리팩터링 방식 뭐였지?" in input_text:
            return "useMemo와 useCallback을 남발하는 리팩터링을 싫어했고, 단순한 구조를 선호했어요."
        if "인증 페이지 리팩터링 얘기했던 거 다시 보자" in input_text:
            return "인증 페이지 쪽에서는 useMemo 남발 같은 리팩터링보다 단순한 구조를 선호했어요."
        if "우리가 왜 sqlite 말고 postgres로 가기로 했지?" in input_text or "우리가 postgres로 가기로 한 이유 다시 말해줘" in input_text:
            return "운영 환경에서 동시성과 트랜잭션 안정성 때문에 sqlite 대신 postgres로 가기로 했어요."
        if "배포 전에 DB 쪽에서 왜 바꾸자고 했는지 기억나?" in input_text:
            return "배포 전에 sqlite에서 postgres로 바꾸자고 한 이유는 동시성과 트랜잭션 안정성 때문이었어요."
        if "인증 쪽 아직 남은 할일 있었나?" in input_text:
            return "남아 있던 건 csrf 정리와 인증 테스트 추가였어요."
        if "그 인증 버그 아직 뭐가 남았지?" in input_text:
            return "남아 있던 건 csrf 정리, 인증 테스트, 세션 만료 뒤 리다이렉트 정리였어요."
        if "로그인 문제 중에서 아직 안 끝난 거 있었지?" in input_text:
            return "아직 안 끝난 건 쿠키 만료 뒤 리다이렉트 UX와 관련 TODO였어요."
        if "남은 할일" in input_text or "안 끝난 거" in input_text:
            return "남아 있던 건 csrf 정리, 인증 테스트 추가, 쿠키 만료 뒤 리다이렉트 UX 정리였어요."
        if "그 인증 버그 다시 보자" in input_text:
            return "로그인 쪽에서는 401, 세션 만료, 리다이렉트 문제가 반복됐고 쿠키 흐름도 확인했어요."
        return "로그인 버그 쪽으로는 401, 세션 만료, 리다이렉트 문제가 계속 언급됐어요."


class AnswerBenchmarkLiveOfflineTests(unittest.TestCase):
    def test_live_answer_benchmark_offline(self) -> None:
        result = evaluate_live_answers(FakeAnswerClient())

        self.assertGreaterEqual(result["llm_summary"]["avg_term_coverage"], 0.7)
        self.assertGreaterEqual(result["llm_summary"]["avg_answer_relevance"], 0.7)
        self.assertGreaterEqual(result["llm_judge_summary"]["avg_point_coverage"], 0.8)
        self.assertGreaterEqual(result["llm_judge_summary"]["avg_groundedness"], 0.9)


if __name__ == "__main__":
    unittest.main()
