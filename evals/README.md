# LabGraph eval harness

The eval harness is the résumé weapon. It runs *before* the KG code exists so
every subsequent change is scored against the same fixed corpus of multi-hop
questions.

## What "passing" means

A question passes when all three deterministic checks hold:

1. Every string in `expected_entities` appears (case-insensitive substring) in
   the SUT's answer text.
2. Every filename in `expected_sources` appears in the retrieved source list.
3. The retrieved sources span at least `min_distinct_sources` distinct
   filenames (default 2 — the multi-hop bar).

No LLM judge. No fuzzy matching. The scorer is boring on purpose so the number
means something.

## Fill in your 20 questions

Edit `evals/questions.yaml`. Delete the three `EXAMPLE` entries. Each question
must reference at least two real files from your lab corpus.

Rules from the design doc, worth restating:

- Write them by hand. Do not generate them with an LLM. If the LLM writes both
  the question and evaluates the system, the eval is worthless.
- Every question must cross at least two source *kinds* (paper + doc, doc +
  slack, paper + email, etc.).
- Store expected entities as they would naturally appear in an answer, not as
  the graph-schema type.

## Run

```bash
# dry-run: parse questions, score them against a null SUT (all fail — sanity check)
python -m evals.runner --questions evals/questions.yaml --sut null

# run against the current LabGraph legacy retrieval baseline (needs a populated SQLite DB)
python -m evals.runner --sut baseline --output-md evals/reports/latest.md

# run graph-aware retrieval (needs docrag.sqlite3 and labgraph.sqlite3)
python -m evals.runner --sut graph --output-md evals/reports/graph.md

# fail CI when the pass rate drops
python -m evals.runner --sut baseline --min-pass-rate 0.75
```

## System Under Test adapters

`evals/sut.py` declares a `SystemUnderTest` protocol and ships three adapters:
`null` for harness checks, `baseline` for legacy vector/FTS retrieval, and
`graph` for graph-aware provenance expansion.
