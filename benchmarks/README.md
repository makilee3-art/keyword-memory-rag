# Benchmarks

평가 케이스를 코드 하드코딩이 아니라 JSON 데이터로 관리한다.

## 파일

- `coding_project_cases.json`: 코딩 프로젝트 장기 대화 회수 케이스
- `ultra_long_cases.json`: 초장기 대화/다량 키워드 회수 케이스

## 필드

- `name`: 케이스 이름
- `query`: 사용자 질문
- `expected_topics`: 상위 retrieval 결과에 꼭 포함되어야 하는 토픽
- `blocked_topics`: 가능하면 상위 retrieval 결과에서 피해야 하는 토픽
- `expected_terms`: 회수된 메모리 본문에 포함되길 기대하는 핵심 단어
- `answer_points`: 최종 답변 평가 시 참고할 포인트
