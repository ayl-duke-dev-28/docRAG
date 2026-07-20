# Structured extraction schema — TDD evidence

## Source and journey

No plan file was provided. The journey was derived from roadmap item 1:

> As the LabGraph extraction pipeline, I need a strict typed response contract
> so an OpenAI structured-output response can be validated before it enters the
> canonical knowledge graph.

## Task report

- RED: `.venv/bin/pytest -q tests/test_labgraph_extraction_schema.py` failed
  during collection because `labgraph.extraction_schema` did not exist.
  Checkpoints: `57c685d`, `ec4d4a9`.
- GREEN: the same command passed all 8 focused tests after the schema models
  were implemented. Checkpoint: `867eec1`.
- Regression: `.venv/bin/pytest -q` passed all 117 project tests.
- Coverage: the focused coverage command reported 94% statement coverage for
  `labgraph/extraction_schema.py`, above the 80% requirement.

## Test specification

| # | What is guaranteed | Test type | Result |
|---|---|---|---|
| 1 | A complete typed entity/relation fragment validates | Unit | PASS |
| 2 | Empty entity and relation arrays form a valid no-result response | Unit | PASS |
| 3 | Unknown entity and relation kinds are rejected | Unit | PASS |
| 4 | Extra object fields are rejected | Unit | PASS |
| 5 | Entity keys are unique and every relation endpoint resolves | Unit | PASS |
| 6 | Relation endpoint kinds follow the LabGraph direction contract | Unit | PASS |
| 7 | Blank entity keys and names are rejected | Unit | PASS |
| 8 | Generated JSON Schema makes all object fields required and forbids extras | Unit | PASS |

## Coverage and known gaps

Command:

```text
.venv/bin/pytest -q tests/test_labgraph_extraction_schema.py \
  --cov=labgraph.extraction_schema --cov-report=term-missing --cov-fail-under=80
```

Result: 8 passed; 94% statement coverage. The two unexecuted validation lines
are the unknown-source-key and self-loop branches. Unknown target keys and the
other graph invariants are covered. API invocation, refusal handling, retries,
and conversion to canonical `Entity`/`Relation` objects intentionally remain
outside this schema-only slice.
