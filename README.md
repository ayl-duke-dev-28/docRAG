# LabGraph (formerly docRAG)

[![CI](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-109%20passing-brightgreen)](./tests)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](./labgraph)

> **LabGraph is the current product direction.** It started as **docRAG**, a
> single-source RAG app (upload PDFs/TXT/MD, ask questions with citations), and
> is now becoming a multi-source knowledge-graph RAG bot for research labs that
> can answer multi-hop questions across papers and Google Docs meeting notes.
> This README tracks what's shipped and what's next.

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

### Legacy retrieval baseline (formerly docRAG)

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
  protocol. `NullSUT` for dry-runs, `LabGraphBaselineSUT` wraps the current
  legacy retrieval path. The KG SUT plugs in later with zero harness changes.
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

- **Runtime identity now says LabGraph** — the FastAPI title, browser title,
  Docker Compose service, smoke-test output, first-screen heading, opening
  assistant message, and query placeholder now frame the app around multi-hop
  lab questions and graph traces instead of the legacy docRAG upload-and-chat
  flow.
- **Environment variables moved to `LABGRAPH_*`** — `.env.example`, Dockerfile,
  and Compose now use `LABGRAPH_DATA_DIR`, `LABGRAPH_EMBEDDING_MODEL`, and
  `LABGRAPH_CHAT_MODEL`. The app still accepts the old `DOCRAG_*` names as
  backward-compatible fallbacks.
- **Design source of truth** — `DESIGN.md` now specifies the product promise,
  visual system, trace component requirements, empty/loading/error states,
  accessibility rules, and implementation order for the LabGraph UI.
- **Trace component foundation** — the answer view now renders graph paths as a
  dedicated ordered trace component with a header, numbered nodes, stacked path
  layout, and visual connectors instead of a thin inline arrow row.
- **Trace relation labels** — `/api/labgraph/query-trace` now returns relation
  metadata between path nodes, and the answer trace renders those relation
  labels as connector chips.
- **Trace entity-kind chips** — trace nodes now show their entity kind
  (`Person`, `Project`, `Method`, `Paper`, or `Decision`) beside the node name,
  using the LabGraph entity palette so paths are easier to scan.
- **The trace is derived from the question** — `/api/query` resolves the
  entities named in the question against the graph, walks between them, and
  returns the trace alongside the answer. Previously the UI fetched a trace in
  a separate call that ignored the question and returned the first
  person→decision path in the graph, so every answer showed the same path.
  An answer and its trace can no longer disagree. Note the scope: the *trace*
  now walks the graph from entities named in the question, but the *answer*
  text still comes from the legacy retrieval baseline. Graph-aware retrieval
  is still Week 4.
- **Designed trace states** — when the question can't be connected to the
  graph, the trace region says which state it's in and what to do next:
  `no_graph`, `no_entities` (nothing in the question matched), `partial` (one
  entity named — shows its neighborhood), `no_path` (names the endpoints
  searched and the depth), and `error` (preserves the answer and sources).
- **Source-to-graph evidence** — sources now show which trace node or relation
  they support when the trace exposes matching filename or chunk provenance.
- **Trace detail disclosure** — trace nodes now expose expandable canonical
  ids, aliases, and attrs; relation connectors expose source/target ids,
  relation kind, provenance chunk IDs, and attrs.
- **Next UI slice** — add graph diagnostics that explain entity matching,
  searched endpoints, and path selection.

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
      Trace visualization in the UI. Shipped so far: the LabGraph chrome pass,
      the trace component, relation labels, entity-kind chips,
      source-to-graph evidence, trace detail disclosure, question-derived
      traces, and the designed states for when a question can't be connected
      to the graph. Next is graph diagnostics.
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

Without an API key, LabGraph uses SQLite full-text search and returns the most
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

# score the current LabGraph legacy retrieval baseline (needs a populated SQLite DB)
python -m evals.runner --sut baseline --output-md evals/reports/latest.md

# CI: fail when pass rate drops below 75%
python -m evals.runner --sut baseline --min-pass-rate 0.75

# unit + integration tests
pytest --cov=evals --cov=labgraph
```

## Multi-hop demo (the proof it works)

Two chunks in — one paper, one meeting note. A **question** goes in, and the
graph resolves a four-node path connecting a person to a decision through a
paper and a method. Nobody hands it the endpoints: it finds them in the
question. This is the exact capability the whole project exists to
demonstrate.

```python
from pathlib import Path
from labgraph import AliasResolver, LabGraph, RegexExtractor, trace_for_question
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

for question in [
    "What did Alex Liu contribute to the March team sync?",
    "What is the capital of France?",
]:
    trace = trace_for_question(g, question, max_depth=4)
    print(f"Q: {question}")
    print(f"   status: {trace.status.value}")
    if trace.path:
        print("   " + " -> ".join(e.id for e in trace.path))
```

Real output (from the current build on `main`):

```
Q: What did Alex Liu contribute to the March team sync?
   status: found
   person:alex-liu -> paper:training-stability-2024 -> method:curriculum-learning -> decision:march-team-sync
Q: What is the capital of France?
   status: no_entities
```

Reading the path: *Alex Liu authored a paper that uses curriculum learning,
and that method was decided in the March team sync.* Four nodes, three
typed edges, one paper + one meeting note bridged. Standard RAG cannot do
this — it retrieves passages, not typed relationships.

The second question is the other half of the proof. It names nothing in the
graph, so it gets `no_entities` rather than a path. A trace that appears no
matter what you ask is decoration; one that can come back empty is evidence.

Once the OpenAI
extractor and KG-aware retrieval land (Weeks 2b + 4), the same traversal
runs on real lab documents against the eval set.

## Architecture

```
app.py              FastAPI app + HTML shell
docrag/             — baseline single-source RAG (shipped)
  config.py         paths and constants
  ingest.py         PDF/TXT/MD → chunks
  storage.py        SQLite + FTS5 index (`data/docrag.sqlite3` legacy filename)
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
  resolve.py        question text → entities named in the graph
  trace.py          question → trace, with designed non-found states
  storage.py        SQLite persistence (save_graph / load_graph)
tests/              — 109 tests, 95% combined coverage
.github/workflows/
  ci.yml            — pytest + eval schema validation on push/PR
```

Not yet built (Weeks 2b–6): OpenAI extractor implementation, Google Drive
ingestion adapter, KG-aware retrieval + KG SUT, graph diagnostics, demo video,
public corpus.

## API

- `GET /api/health`
- `GET /api/documents`
- `POST /api/upload` with multipart field `files`
- `POST /api/query` with JSON `{ "question": "...", "top_k": 6 }` — returns
  `{ answer, sources, mode, trace }`, where `trace` is derived from `question`.
  Trace path nodes include `id`, `kind`, `name`, `aliases`, and `attrs`;
  relation provenance uses chunk IDs, which the UI uses to label which sources
  support graph nodes or edges.
- `GET /api/labgraph/stats`
- `GET /api/labgraph/entities?kind=method`
- `POST /api/labgraph/query-trace` with either `{ "question": "..." }` or an
  explicit `{ "source_id": "...", "target_id": "..." }` pair.
