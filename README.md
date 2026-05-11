# keyword-memory-rag

A prototype for long-conversation memory retrieval using topic and keyword memory instead of pure vector similarity.

## Why

Pure vector RAG often misses long-range personal or project context.

Examples:
- Months ago: diet, calories, weight loss
- Now: "I want chicken today"

- Weeks ago: sqlite vs postgres tradeoff
- Now: "Why did we switch again?"

This project explores a different approach:
- store evicted conversation chunks as structured memory
- attach multiple keywords and topic paths
- rank by full-query-to-topic matching
- traverse memories progressively until enough context is found

## Core Idea

Instead of:
- query -> nearest vector chunks

This project does:
- query -> topic candidates
- topic candidates -> related memory buckets
- memory buckets -> relevance + recency + salience ranking
- stop when enough context is collected

## Features

- SQLite-backed memory store
- topic hierarchy + keyword index
- relevance + recency hybrid ranking
- topic diversity penalty
- hard negative benchmark cases
- answer benchmark
- heuristic vs LLM answer comparison
- LLM judge for answer quality

## Project Structure

- [src/keyword_memory.py](/E:/nez/keywordset%20rag/src/keyword_memory.py): core retrieval logic
- [scripts/live_chat_test.py](/E:/nez/keywordset%20rag/scripts/live_chat_test.py): live API test for personal-memory style conversations
- [scripts/coding_project_live_test.py](/E:/nez/keywordset%20rag/scripts/coding_project_live_test.py): live API test for coding-project conversations
- [scripts/benchmark_metrics.py](/E:/nez/keywordset%20rag/scripts/benchmark_metrics.py): retrieval metrics
- [scripts/answer_benchmark.py](/E:/nez/keywordset%20rag/scripts/answer_benchmark.py): offline answer evaluation
- [scripts/answer_benchmark_live.py](/E:/nez/keywordset%20rag/scripts/answer_benchmark_live.py): heuristic vs LLM answer comparison
- [benchmarks/](/E:/nez/keywordset%20rag/benchmarks): benchmark case definitions
- [tests/](/E:/nez/keywordset%20rag/tests): automated tests

## Benchmarks

Included benchmark sets:
- coding-project long-context cases
- ultra-long noisy memory cases
- hard negative overlap cases

Retrieval metrics:
- Recall@3
- Precision@3
- MRR
- blocked topic rate

Answer metrics:
- term coverage
- answer relevance
- LLM-judged point coverage
- LLM-judged groundedness

## Run

```powershell
python -m unittest -v
python scripts/benchmark_metrics.py
python scripts/answer_benchmark.py
python scripts/live_chat_test.py
python scripts/coding_project_live_test.py
python scripts/answer_benchmark_live.py
```

## Benchmark Data

- [benchmarks/coding_project_cases.json](/E:/nez/keywordset%20rag/benchmarks/coding_project_cases.json)
- [benchmarks/ultra_long_cases.json](/E:/nez/keywordset%20rag/benchmarks/ultra_long_cases.json)
- [benchmarks/hard_cases.json](/E:/nez/keywordset%20rag/benchmarks/hard_cases.json)

## Current Limitations

- topic definitions are hand-authored
- intent boosts are still heuristic
- benchmark sets are still small
- the LLM judge can be biased
- there is not yet a vector-only baseline comparison

## Next Steps

- larger benchmark datasets
- file-based real conversation imports
- stronger answer synthesis
- direct comparison against vector-only RAG
