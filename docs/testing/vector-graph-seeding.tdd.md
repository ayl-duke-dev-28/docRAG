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

## Follow-up: bounded seed expansion

`expand_chunk_seed_neighborhood` now composes provenance-backed seed selection
with an undirected, depth-bounded graph neighborhood.

| Guarantee | Test | Type | Result |
|---|---|---|---|
| Ranked seeds appear first and inbound/outbound neighbors follow without duplicates. | `test_expand_chunk_seeds_walks_both_directions_with_seeds_first` | Unit | PASS |
| Depth zero returns seeds only, and unknown chunks remain empty. | `test_expand_chunk_seeds_respects_zero_depth_and_unknown_chunks` | Unit | PASS |

- **RED:** `.venv/bin/pytest -q tests/test_labgraph_seed.py` failed during
  collection because `expand_chunk_seed_neighborhood` did not exist.
- **GREEN and coverage:**
  `COVERAGE_FILE=/tmp/docrag_seed_expansion_coverage .venv/bin/pytest -q --cov=labgraph.seed --cov-report=term-missing`
  — `147 passed`; `labgraph/seed.py` coverage `100%`.
- **Checkpoint note:** the workspace grants read-only access to `.git`, so
  RED/GREEN checkpoint commits could not be created.

The remaining integration step is to use the expanded entities when selecting
provenance chunks for answer context.
