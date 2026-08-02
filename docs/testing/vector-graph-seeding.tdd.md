# Vector-to-graph seed TDD evidence

## Source and journey

No plan file was provided. This slice was derived from the remaining Week 4
vector-seeded retrieval work:

> As the retrieval pipeline, I want to map ranked retrieved chunks to graph
> entities supported by their relation provenance, so that later traversal can
> begin from vector/FTS evidence rather than requiring exact entity mentions.

## RED / GREEN report

| Guarantee | Test | Type | Result |
|---|---|---|---|
| Chunk rank is preserved while relation endpoints are deduplicated. | `test_seed_entities_preserves_chunk_rank_and_deduplicates` | Unit | PASS |
| Numeric chunk IDs match stored string provenance. | `test_seed_entities_preserves_chunk_rank_and_deduplicates` | Unit | PASS |
| Empty and unknown chunk IDs return no seeds. | `test_seed_entities_returns_empty_for_no_matching_chunks` | Unit | PASS |

- **RED:** `.venv/bin/pytest -q tests/test_labgraph_seed.py` failed during
  collection because `labgraph.seed` did not exist.
- **GREEN and coverage:**
  `COVERAGE_FILE=/tmp/docrag_seed_coverage .venv/bin/pytest -q --cov=labgraph.seed --cov-report=term-missing`
  — `145 passed`; `labgraph/seed.py` coverage `100%`.
- **Checkpoint note:** the workspace grants read-only access to `.git`, so
  RED/GREEN checkpoint commits could not be created.

## Known gap

This slice provides the deterministic seed-selection primitive only. Wiring
those seeds into bounded graph traversal and answer retrieval is the next
step.
