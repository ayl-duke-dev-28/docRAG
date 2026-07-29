# Graph-aware retrieval TDD evidence

## Source and journey

No plan file was provided. This slice was derived from the next open roadmap
item, Week 4 graph-aware retrieval:

> As a lab member, I want answer context to include the chunks that support the
> graph path for my question, so that multi-hop evidence is not lost behind the
> baseline retrieval ranking.

## RED / GREEN report

| Guarantee | Test | Type | Result |
|---|---|---|---|
| Path-provenance chunks are prioritized in relation order and duplicate baseline chunks are removed. | `test_graph_aware_retrieval_prioritizes_path_provenance_and_deduplicates` | Unit | PASS |
| A question unrelated to the graph preserves baseline retrieval unchanged. | `test_graph_aware_retrieval_keeps_baseline_for_unrelated_question` | Unit | PASS |
| The query endpoint uses one loaded graph for both answering and its visible trace. | `test_query_endpoint_uses_the_loaded_graph_for_answering` | Integration | PASS |
| A graph-load failure preserves the baseline answer and returns an error trace. | `test_query_endpoint_keeps_the_answer_when_the_graph_trace_fails` | Integration | PASS |

- **RED:** `pytest -q tests/test_graph_aware_retrieval.py tests/test_labgraph_api.py`
  executed the new unit tests and failed because
  `retrieve_graph_aware` did not exist. The global interpreter also lacked
  optional project dependencies, so integration verification moved to the
  repository virtual environment.
- **GREEN:** `.venv/bin/pytest -q tests/test_graph_aware_retrieval.py tests/test_labgraph_api.py`
  — `13 passed`.
- **Full suite and coverage:**
  `.venv/bin/pytest -q --cov=docrag.retrieval --cov=labgraph --cov-report=term-missing`
  — `140 passed`; combined measured coverage `87%`.

## Known gap

This is the first bounded Week 4 slice. The graph path is resolved from entity
mentions in the question; vector-seeded entity discovery and the first KG eval
score remain follow-up work.

## Follow-up: graph-aware eval SUT

The next small slice added `LabGraphGraphAwareSUT`, selectable with
`python -m evals.runner --sut graph`.

| Guarantee | Test | Type | Result |
|---|---|---|---|
| The `graph` alias selects the graph-aware SUT. | `test_get_sut_graph` | Unit | PASS |
| The SUT loads the configured graph and passes it, the question, and `top_k` into `answer()`, preserving answer text and source filenames. | `test_graph_sut_loads_the_graph_for_answering` | Unit | PASS |

- **RED:** `.venv/bin/pytest -q tests/test_evals_runner.py` failed during
  collection because `LabGraphGraphAwareSUT` did not exist.
- **GREEN:** the same command completed with `9 passed`.
- **Full suite and coverage:**
  `COVERAGE_FILE=/tmp/docrag_graph_sut_coverage .venv/bin/pytest -q --cov=evals.sut --cov-report=term-missing`
  — `142 passed`; `evals/sut.py` coverage `85%`.
- **Checkpoint note:** the workspace grants read-only access to `.git`, so
  RED/GREEN checkpoint commits could not be created for this follow-up.
