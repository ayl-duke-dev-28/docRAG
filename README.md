# docRAG → LabGraph (work in progress)

[![CI](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-79%20passing-brightgreen)](./tests)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](./labgraph)

> **I'm actively rebuilding this project.** It started as **docRAG**, a
> single-source RAG app (upload PDFs/TXT/MD, ask questions with citations).
> I'm turning it into **LabGraph**, a multi-source knowledge-graph RAG bot
> for research labs that can answer multi-hop questions across papers and
> Google Docs meeting notes. This README tracks what's shipped and what's next.

**Target:** answer questions like *"Which of our published methods came out of
the March team sync?"* with an answer AND a visible graph-traversal trace
(e.g. `paper A → method:curriculum-learning → decided_in → notes 2024-03-14`).

## Why this exists

Standard RAG chatbots have two failure modes inside a research lab:

1. **Doc-count ceiling.** Retrieval stuffs chunks into a prompt, capping at
   ~10–100 docs before context runs out.
2. **No cross-source reasoning.** Questions that require touching a paper AND
   a meeting note need entity-level stitching, not passage-level stitching.

LabGraph replaces the retrieval step with a small typed knowledge graph
(`Person`, `Project`, `Method`, `Paper`, `Decision` + six relations), walks it
at query time, and returns both the answer and the path.

## What's shipped so far

### Baseline docRAG (the starting point I'm building on)

- **FastAPI web app** — upload PDFs / TXT / Markdown at `http://127.0.0.1:8000`.
- **Ingestion pipeline** — `docrag/ingest.py` chunks documents by page with
  overlap; content-hash dedupe prevents re-ingesting the same file.
- **SQLite storage** — `docrag/storage.py` persists documents, chunks, and
  embeddings; FTS5 virtual table for keyword search.
- **Hybrid retrieval** — `docrag/retrieval.py` uses OpenAI embeddings +
  cosine similarity when the API key is present, falls back to BM25 FTS
  otherwise.
- **LLM synthesis with citations** — `docrag/llm.py` calls OpenAI chat with
  the retrieved chunks and returns a source-linked answer.
- **Document management UI** — search, filter, rename, delete.
- **Docker Compose** — `docker compose up --build` and go.

### New: eval harness (Week 1 of the LabGraph plan)

- **`evals/questions.yaml`** — hand-labeled multi-hop questions with expected
  entities, expected sources, and a `min_distinct_sources` bar for enforcing
  the multi-hop requirement. Ships with 3 clearly-marked EXAMPLE questions;
  the real 20 replace them.
- **Deterministic scorer** — `evals/scorer.py` scores pass/fail on three
  checks: every expected entity appears in the answer text (case-insensitive),
  every expected source appears in the retrieved set, and the retrieved set
  spans ≥ `min_distinct_sources` distinct filenames. No LLM judge.
- **Pluggable System Under Test** — `evals/sut.py` declares a `SystemUnderTest`
  protocol. `NullSUT` for dry-runs, `DocragBaselineSUT` wraps the current
  retrieval. The KG SUT plugs in later with zero harness changes.
- **CLI runner** — `python -m evals.runner` with `--sut`, `--output-md`,
  `--output-json`, `--min-pass-rate` (returns exit 1 in CI when the score
  drops).
- **Reports** — Markdown + JSON output showing per-question pass/fail and the
  specific reason for each failure.
- **Tests** — 32 unit + integration tests, 93% coverage on `evals/`.

### New: labgraph — the typed knowledge graph (Week 2)

The pure-Python core of the LabGraph pipeline. Ships without any LLM
dependency so CI can exercise the full extract → build → traverse → persist
loop on every push.

- **`labgraph/schema.py`** — the 5-entity / 6-relation contract from the
  design doc, encoded as `EntityKind` and `RelationKind` enums plus frozen
  `Entity` and `Relation` dataclasses. `canonical_id(kind, name)` gives every
  node a stable, slugged identifier.
- **`labgraph/aliases.py`** — `AliasResolver` reads
  `labgraph/aliases.yaml` and collapses surface forms ("Alex Liu",
  "A. Liu", "aliu@duke.edu") to one canonical id per kind. Aggressive
  normalization (case, punctuation, whitespace) so a Google Doc that misspells
  a name still lands on the right node.
- **`labgraph/graph.py`** — `LabGraph` wraps `networkx.MultiDiGraph` so
  multiple relation kinds can coexist between the same pair. Exposes
  `add_entity` (idempotent merge — re-ingesting grows the alias set instead
  of duplicating), `add_relation`, `neighbors`, `neighborhood`, and
  `shortest_path` for depth-bounded multi-hop lookup.
- **`labgraph/extract.py`** — `Extractor` protocol with two implementations:
  a **`RegexExtractor`** (deterministic, dependency-free — used by tests and
  CI so no OpenAI credits are burned per run) and an **`OpenAIExtractor`**
  stub that lands as a real structured-outputs call in the next slice.
  `extract_many` batches chunks and dedupes entities.
- **`labgraph/storage.py`** — `save_graph` / `load_graph` persist the graph
  to a dedicated SQLite file (`labgraph_entities` + `labgraph_relations`
  tables with the right indexes). Round-trip preserves aliases, attrs, and
  provenance chunk IDs.
- **Verified end-to-end** — the [Multi-hop demo](#multi-hop-demo-the-proof-it-works)
  section below shows the runnable snippet and its actual output.
- **47 new tests, 95% coverage on `labgraph/`.**

### New: LabGraph UI foundation

- **Visible app chrome now says LabGraph** — the browser title, first-screen
  heading, opening assistant message, and query placeholder now frame the app
  around multi-hop lab questions and graph traces instead of the legacy docRAG
  upload-and-chat flow.
- **Design source of truth** — `DESIGN.md` now specifies the product promise,
  visual system, trace component requirements, empty/loading/error states,
  accessibility rules, and implementation order for the LabGraph UI.
- **Next UI slice** — replace the current inline trace row with a proper graph
  trace component that shows entity kinds, relation labels, and no-path/error
  states.

### New: continuous integration

- **`.github/workflows/ci.yml`** — the workflow that keeps the eval story
  honest. Runs on every push and pull request to `main`, across a Python
  **3.11 + 3.12 matrix**, using pip cache keyed on `requirements.txt`.
- **What it enforces:**
  - `pytest --cov=evals --cov-fail-under=80` — hard-fails CI if coverage on
    the eval package drops below 80%.
  - `python -m evals.runner --sut null` — parses `evals/questions.yaml` end
    to end, so a malformed question schema breaks the build instead of
    silently rotting.
  - Every eval run in CI uploads its Markdown + JSON reports to
    `evals/reports/` as build artifacts (retained 14 days), so any PR that
    changes the score leaves a downloadable trail.
- **Why it's here at Week 1:** the design doc calls the eval harness the
  résumé weapon. That's only true if the harness runs on every commit, not
  just when I remember to invoke it. CI turns the eval set into an actual
  gate.
- **Current status:** the badge at the top of this README reflects the live
  build on `main`. Green means the eval schema is valid, tests pass, and
  coverage is above the floor.

## Roadmap

- [x] **Week 1 — Eval harness.** Scoring infrastructure before any KG code.
- [x] **Week 2 — Extraction + KG builder.** Fixed 5-entity, 6-relation schema.
      NetworkX in memory, persisted to SQLite. Deterministic regex extractor
      for CI; OpenAI structured-outputs extractor to follow.
- [ ] **Week 2b — OpenAI extractor.** Replace the regex baseline with a
      structured-outputs LLM call per chunk. Same `Extractor` protocol, no
      pipeline changes downstream.
- [ ] **Week 3 — Google Drive ingestion.** OAuth flow, Docs → chunks → graph.
- [ ] **Week 4 — Graph-aware retrieval.** Hybrid vector seed + bounded BFS
      along typed edges. First real eval score against the KG.
- [ ] **Week 5 — Prompt + retrieval iteration** until eval hits **≥ 15 / 20**.
      Trace visualization in the UI. The first LabGraph chrome pass is shipped;
      the next UI slice is a richer graph trace component.
- [ ] **Week 6 — Demo video + reproducible public corpus + release.**

## Quick start

### Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8000`. Uploaded files and the SQLite index live in `data/`.

### Local

Mac/Linux:

```bash
./scripts/start.sh
```

Windows:

```bat
scripts\start.bat
```

### LLM mode (optional)

Without an API key, docRAG uses SQLite full-text search and returns the most
relevant passages directly. For synthesized answers and semantic embeddings,
edit `.env`:

```text
OPENAI_API_KEY=your_key_here
```

Restart with `docker compose down && docker compose up --build`. If you built
before pinning the OpenAI dependency, `docker compose build --no-cache` once
to force a clean install.

## Running the eval harness

Multi-hop questions are the specification. See `evals/README.md` for the
schema and rules.

```bash
# dry-run: parse questions, score against a null SUT (all fail — sanity check)
python -m evals.runner --questions evals/questions.yaml --sut null

# score the current docrag baseline (needs a populated SQLite DB)
python -m evals.runner --sut baseline --output-md evals/reports/latest.md

# CI: fail when pass rate drops below 75%
python -m evals.runner --sut baseline --min-pass-rate 0.75

# unit + integration tests
pytest --cov=evals --cov=labgraph
```

## Multi-hop demo (the proof it works)

Two chunks in — one paper, one meeting note. The graph resolves a four-node
path connecting a person to a decision through a paper and a method. This is
the exact capability the whole project exists to demonstrate.

```python
from pathlib import Path
from labgraph import AliasResolver, LabGraph, RegexExtractor
from labgraph.extract import Chunk, extract_many

aliases = AliasResolver.from_yaml(Path("labgraph/aliases.yaml"))
chunks = [
    Chunk(id="c1", filename="training_stability_2024.pdf",
          text="Alex Liu introduced curriculum learning to fix training instability."),
    Chunk(id="c2", filename="2024-03-14-team-sync.docx",
          text="In the March team sync we decided to adopt curriculum learning."),
]

result = extract_many(RegexExtractor(aliases=aliases), chunks)
g = LabGraph()
for e in result.entities: g.add_entity(e)
for r in result.relations: g.add_relation(r)

path = g.shortest_path("person:alex-liu", "decision:march-team-sync", max_depth=4)
print(f"entities={g.entity_count} relations={g.relation_count}")
print(" -> ".join(path))
```

Real output (from the current build on `main`):

```
entities=5 relations=4
person:alex-liu -> paper:training-stability-2024 -> method:curriculum-learning -> decision:march-team-sync
```

Reading the path: *Alex Liu authored a paper that uses curriculum learning,
and that method was decided in the March team sync.* Four nodes, three
typed edges, one paper + one meeting note bridged. Standard RAG cannot do
this — it retrieves passages, not typed relationships. Once the OpenAI
extractor and KG-aware retrieval land (Weeks 2b + 4), the same traversal
runs on real lab documents against the eval set.

## Architecture

```
app.py              FastAPI app + HTML shell
docrag/             — baseline single-source RAG (shipped)
  config.py         paths and constants
  ingest.py         PDF/TXT/MD → chunks
  storage.py        SQLite + FTS5 index
  retrieval.py      hybrid vector + BM25 retrieval (baseline SUT)
  llm.py            OpenAI embeddings + chat wrapper
evals/              — eval harness (shipped, Week 1)
  schema.py         Question / Answer / QuestionResult dataclasses
  loader.py         YAML → Question tuple
  sut.py            SystemUnderTest protocol + baseline adapter
  scorer.py         deterministic pass/fail scorer
  runner.py         CLI entry point
  report.py         Markdown + JSON reports
labgraph/           — typed knowledge graph (shipped, Week 2)
  schema.py         Entity / Relation / EntityKind / RelationKind
  aliases.py        AliasResolver + YAML loader
  aliases.yaml      alias declarations (starter file)
  graph.py          NetworkX MultiDiGraph wrapper + multi-hop traversal
  extract.py        Extractor protocol + RegexExtractor + OpenAIExtractor stub
  storage.py        SQLite persistence (save_graph / load_graph)
tests/              — 79 tests, 95% combined coverage
.github/workflows/
  ci.yml            — pytest + eval schema validation on push/PR
```

Not yet built (Weeks 2b–6): OpenAI extractor implementation, Google Drive
ingestion adapter, KG-aware retrieval + KG SUT, trace visualization, demo
video, public corpus.

## API

- `GET /api/health`
- `GET /api/documents`
- `POST /api/upload` with multipart field `files`
- `POST /api/query` with JSON `{ "question": "...", "top_k": 6 }`
