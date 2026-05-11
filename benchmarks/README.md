# Benchmarks

This folder contains benchmark case definitions for retrieval and answer evaluation.

## Files

- `coding_project_cases.json`: long-context coding project cases
- `ultra_long_cases.json`: ultra-long noisy memory cases
- `hard_cases.json`: hard negative overlap cases

## Fields

- `name`: case name
- `query`: user question
- `expected_topics`: topics that should appear in the top retrieval results
- `blocked_topics`: topics that should not dominate the top retrieval results
- `expected_terms`: key terms that should appear in the retrieved memories
- `answer_points`: expected answer content for answer evaluation
