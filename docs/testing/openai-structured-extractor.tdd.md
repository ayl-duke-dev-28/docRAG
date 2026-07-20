# OpenAI structured extractor — TDD evidence

## Source and journey

No plan file was provided. The journey was derived from the next Week 2b
milestone:

> As the LabGraph ingestion pipeline, I need one validated structured-output
> extraction per chunk so real documents can become canonical graph entities
> and provenance-backed relations.

## Task report

- RED: `.venv/bin/pytest -q tests/test_labgraph_extract.py` failed during
  collection because `OpenAIExtractionError` and the implemented flow did not
  exist. Checkpoints: `f1615a1`, `ef7ff89`.
- GREEN: the same focused command passed 14 tests after implementation.
  Checkpoint: `0d2b6fd`.
- SDK verification: OpenAI Python `2.46.0` exposes `client.responses.parse`.
- Regression: `.venv/bin/pytest -q` passed all 122 project tests.
- Coverage: 22 focused schema/extractor tests reported 91% combined statement
  coverage, above the 80% requirement.

## Test specification

| # | What is guaranteed | Test type | Result |
|---|---|---|---|
| 1 | One request uses the configured model and `StructuredExtraction` response type | Unit | PASS |
| 2 | The request includes the chunk filename, identifier, and text | Unit | PASS |
| 3 | Parsed entities use alias-aware canonical IDs and retain metadata | Unit | PASS |
| 4 | Parsed relations use canonical endpoints and carry chunk provenance | Unit | PASS |
| 5 | Empty structured output returns an empty extraction result | Unit | PASS |
| 6 | Model refusals produce a clear extractor-specific exception | Unit | PASS |
| 7 | Missing or malformed parsed output is rejected | Unit | PASS |
| 8 | OpenAI SDK errors are wrapped without making CI network calls | Unit | PASS |

## Coverage and known gaps

Command:

```text
.venv/bin/pytest -q tests/test_labgraph_extract.py \
  tests/test_labgraph_extraction_schema.py \
  --cov=labgraph.extract --cov=labgraph.extraction_schema \
  --cov-report=term-missing --cov-fail-under=80
```

Result: 22 passed; 91% combined statement coverage. Runtime selection of the
OpenAI extractor and live-key integration testing intentionally remain outside
this slice. Production calls require `OPENAI_API_KEY`; tests inject a fake
client and never contact the API.
