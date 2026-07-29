# LabGraph (formerly docRAG)

[![CI](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/ayl-duke-dev-28/docRAG/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-143%20passing-brightgreen)](./tests)
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
  legacy retrieval path, and `LabGraphGraphAwareSUT` scores the graph-aware
  answer path with `--sut graph`.
- **CLI runner** — `python -m evals.runner` with `--sut`, `--output-md`,
  `--output-json`, `--min-pass-rate` (returns exit 1 in CI when the score
  drops).
- **Reports** — Markdown + JSON output showing per-question pass/fail and the
  specific reason for each failure.
- **Tests** — 32 unit + integration tests, 93% coverage on `evals/`.

### New: labgraph — the typed knowledge graph (Week 2)

The graph core keeps a deterministic offline path, so CI can exercise the full
extract → build → traverse → persist loop on every push without an API key.
The optional OpenAI path uses the same extractor contract for real-document
entity and relation extraction.

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
  that makes one Responses API structured-output call per chunk, converts the
  validated response into canonical graph objects, and attaches chunk
  provenance to every relation. `extract_many` batches chunks and dedupes
  entities.
- **`labgraph/extraction_schema.py`** — strict Pydantic response models for
  the OpenAI extractor. The generated JSON Schema requires every field,
  rejects unknown fields and enum values, validates local entity references,
  and enforces the allowed direction of all six relation kinds.
- **`labgraph/storage.py`** — `save_graph` / `load_graph` persist the graph
  to a dedicated SQLite file (`labgraph_entities` + `labgraph_relations`
  tables with the right indexes). Round-trip preserves aliases, attrs, and
  provenance chunk IDs.
- **Verified end-to-end** — the [Multi-hop demo](#multi-hop-demo-the-proof-it-works)
  section below shows the runnable snippet and its actual output.
- **60 new tests, 95% coverage on `labgraph/`.**

### New: configurable runtime extraction (Week 2b)

The production upload path now turns every stored document chunk into graph
entities and relations with the configured extractor:

- **Automatic selection** — `LABGRAPH_EXTRACTOR=auto` uses
  `OpenAIExtractor` when `OPENAI_API_KEY` is present and `RegexExtractor`
  otherwise.
- **Explicit modes** — set `LABGRAPH_EXTRACTOR=regex` for deterministic,
  network-free ingestion or `LABGRAPH_EXTRACTOR=openai` to require structured
  extraction. Explicit OpenAI mode fails fast when no API key is configured.
- **Independent model configuration** — `LABGRAPH_EXTRACTION_MODEL` selects
  the structured-output model without changing the chat or embedding models.
- **Existing pipeline contract** — both modes feed the same `Extractor`
  protocol into `extract_many`, then merge the canonical entities and
  provenance-backed relations into `data/labgraph.sqlite3`.
- **Safe failure behavior** — if graph extraction fails, ingestion removes the
  new document rows and copied upload so retrying does not report a
  half-ingested document as a duplicate.
- **Verified offline** — runtime selection, invalid configuration, ingestion
  wiring, and rollback behavior are covered without making network requests.
  The full suite currently passes **143 tests**.

### New: Google Drive ingestion (Week 3)

- **Read-only OAuth flow** — the corpus panel can connect a Google account
  with an expiring, one-time OAuth state value and offline refresh access.
- **Credential safety** — tokens are stored under `LABGRAPH_DATA_DIR`, outside
  the source tree, with owner-only file permissions. Invalid credentials put
  the UI back into its reconnect state.
- **Drive document picker** — connected users can browse their Google Docs,
  select one or more documents, and import them from the LabGraph workspace.
- **Docs → chunks → graph** — Google Docs export as plain text and enter the
  existing Markdown ingestion path, so content-hash dedupe, chunking,
  embeddings, structured extraction, provenance, and graph persistence behave
  exactly like local uploads.
- **Network-free tests** — OAuth state validation and replay rejection,
  credential persistence, Drive pagination, document export, API endpoints,
  and ingestion reuse are covered with fake services. See the
  [Week 3 TDD evidence](docs/testing/google-drive-ingestion.tdd.md).

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
  An answer and its trace can no longer disagree. The first graph-aware
  retrieval slice now also uses this path to select answer context.
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
- **Graph diagnostics** — each trace now exposes status, matched entities,
  searched endpoints, max depth, returned path size, and the path-selection
  rule.

### New: graph-aware retrieval foundation (Week 4)

`/api/query` now loads the persisted graph once and uses that same snapshot for
both answer retrieval and the visible trace:

- **Baseline seed retrieval** — the existing semantic-vector path remains the
  first retrieval step when embeddings are available, with FTS/BM25 as its
  network-free fallback.
- **Bounded graph traversal** — entities named in the question are resolved
  against the graph, then connected through the existing depth-bounded typed
  path search.
- **Provenance expansion** — chunk IDs attached to relations along the selected
  path are loaded as answer context and placed ahead of baseline-only results.
  This lets evidence from both sides of a multi-hop path survive the initial
  retrieval ranking.
- **Stable deduplication and limit** — a provenance chunk that was already
  returned by vector/FTS retrieval appears once, and the combined result still
  respects `top_k`.
- **Honest fallback** — questions with no complete graph path return the
  baseline sources unchanged. If the graph cannot be loaded, the answer is
  preserved and the trace reports its existing `error` state.
- **One graph snapshot per query** — answer context and trace generation reuse
  the same loaded graph, preventing them from observing different graph state
  during one request.
- **Graph-aware eval adapter** — `LabGraphGraphAwareSUT` loads the persisted
  graph and sends it through the same `answer(..., graph=graph)` path used by
  the API. Select it with `--sut graph` to compare graph-aware retrieval
  against the legacy `--sut baseline` on the same questions. One eval run
  lazily loads and reuses a single graph snapshot across every question.
- **TDD coverage** — focused unit and API integration tests cover ordering,
  deduplication, unrelated-question fallback, shared graph use, and graph-load
  failure, plus graph-SUT selection and execution. See the
  [graph-aware retrieval TDD evidence](docs/testing/graph-aware-retrieval.tdd.md).

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
      for CI; the OpenAI structured-output implementation now exists as the
      Week 2b production path.
- [x] **Week 2b — OpenAI extractor.** Replace the regex baseline with a
      structured-outputs LLM call per chunk. Same `Extractor` protocol, no
      pipeline changes downstream. Includes the strict entity/relation
      response schema, reference validation, relation-direction checks, the
      Responses API call, canonical conversion, provenance, and refusal/error
      handling, plus configurable runtime ingestion selection.
- [x] **Week 3 — Google Drive ingestion.** Read-only OAuth flow, Drive document
      picker, and Docs → chunks → graph through the shared ingestion pipeline.
- [ ] **Week 4 — Graph-aware retrieval.** Hybrid vector seed + bounded BFS
      along typed edges. First real eval score against the KG. Shipped so far:
      answer context prioritizes the provenance chunks along a question-derived
      bounded graph path, deduplicates them against baseline vector/FTS
      results, falls back unchanged when no graph path is found, and can be
      evaluated independently with `--sut graph`. Each graph eval lazily loads
      one persisted graph snapshot and reuses it across all questions.
- [ ] **Week 5 — Prompt + retrieval iteration** until eval hits **≥ 15 / 20**.
      Trace visualization in the UI. Shipped so far: the LabGraph chrome pass,
      the trace component, relation labels, entity-kind chips,
      source-to-graph evidence, trace detail disclosure, question-derived
      traces, and the designed states for when a question can't be connected
      to the graph, plus graph diagnostics.
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

Without an API key, LabGraph uses SQLite full-text search, returns the most
relevant passages directly, and builds its graph with the deterministic regex
extractor. To enable synthesized answers, semantic embeddings, and structured
graph extraction, edit `.env`:

```text
OPENAI_API_KEY=your_key_here
LABGRAPH_EXTRACTOR=auto
LABGRAPH_EXTRACTION_MODEL=gpt-4o-mini
```

`LABGRAPH_EXTRACTOR` accepts `auto`, `regex`, or `openai`. The default `auto`
uses OpenAI when `OPENAI_API_KEY` is set and regex otherwise. Use `regex` to
force network-free ingestion; explicit `openai` mode fails fast without a key.

Restart with `docker compose down && docker compose up --build`. If you built
before pinning the OpenAI dependency, `docker compose build --no-cache` once
to force a clean install.

To exercise the OpenAI extractor directly with `OPENAI_API_KEY` exported:

```python
from labgraph import OpenAIExtractor
from labgraph.extract import Chunk

result = OpenAIExtractor().extract(
    Chunk(
        id="paper-1-page-1",
        filename="training_stability.pdf",
        text="Alex Liu introduced curriculum learning to stabilize training.",
    )
)

for entity in result.entities:
    print(entity.id, entity.kind.value, entity.name)
for relation in result.relations:
    print(relation.source_id, relation.kind.value, relation.target_id)
```

The response is validated against `StructuredExtraction` before conversion.
Refusals, invalid structured output, and API failures raise
`OpenAIExtractionError`; every converted relation records the input chunk ID
as provenance.

### Google Drive ingestion

First, enable the Google Drive API and create an OAuth 2.0 **Web application**
client in Google Cloud. Add this exact authorized redirect URI:

```text
http://127.0.0.1:8000/api/google-drive/callback
```

Then add the client credentials to `.env`:

```text
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/google-drive/callback
```

Restart LabGraph, select **Connect** in the Google Drive section, complete
consent, then choose Docs to import. LabGraph requests the read-only Drive
scope; stored OAuth credentials live at
`data/google-drive-credentials.json` by default. The redirect URI must match
the Google Cloud configuration exactly.

Operational behavior:

- Imports are user-triggered; background Drive synchronization is not included.
- A batch can contain up to 25 Google Docs.
- Importing unchanged content returns the existing document as a duplicate.
  Importing a changed Doc creates a new indexed version.
- `GOOGLE_CREDENTIALS_PATH` can override the credential-file location.
- **Disconnect** deletes LabGraph's local credentials. It does not revoke the
  Google account grant; revoke that separately from the Google account if
  required.

Setup references:
[Google OAuth for web server applications](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Google Drive API files](https://developers.google.com/workspace/drive/api/reference/rest/v3/files).

## Running the eval harness

Multi-hop questions are the specification. See `evals/README.md` for the
schema and rules.

```bash
# dry-run: parse questions, score against a null SUT (all fail — sanity check)
python -m evals.runner --questions evals/questions.yaml --sut null

# score the current LabGraph legacy retrieval baseline (needs a populated SQLite DB)
python -m evals.runner --sut baseline --output-md evals/reports/latest.md

# score graph-aware retrieval against the same questions (needs both SQLite DBs)
python -m evals.runner --sut graph --output-md evals/reports/graph.md

# CI: fail when pass rate drops below 75%
python -m evals.runner --sut baseline --min-pass-rate 0.75

# unit + integration tests
pytest --cov=evals --cov=labgraph
```

The `graph` SUT loads `labgraph.sqlite3` on its first question and reuses that
in-memory snapshot for the rest of the run. This avoids repeated database
loads and ensures every question in one report is scored against identical
graph state.

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

The first Week 4 retrieval slice now uses this traversal to promote the
relations' provenance chunks into answer context, and `--sut graph` can score
that path. Vector-seeded entity discovery and the first score over the real
eval corpus remain the next steps.

## Architecture

```
app.py              FastAPI app + HTML shell
docrag/             — baseline single-source RAG (shipped)
  config.py         paths and constants
  ingest.py         PDF/TXT/MD → chunks
  google_drive.py   OAuth + Google Docs listing/export adapter
  storage.py        SQLite + FTS5 index (`data/docrag.sqlite3` legacy filename)
  retrieval.py      vector/FTS seeds + graph-provenance context expansion
  llm.py            OpenAI embeddings + chat wrapper
evals/              — eval harness (shipped, Week 1)
  schema.py         Question / Answer / QuestionResult dataclasses
  loader.py         YAML → Question tuple
  sut.py            null, baseline, and graph-aware SUT adapters
  scorer.py         deterministic pass/fail scorer
  runner.py         CLI entry point
  report.py         Markdown + JSON reports
labgraph/           — typed knowledge graph (shipped, Week 2)
  schema.py         Entity / Relation / EntityKind / RelationKind
  extraction_schema.py  strict OpenAI structured-output response contract
  aliases.py        AliasResolver + YAML loader
  aliases.yaml      alias declarations (starter file)
  graph.py          NetworkX MultiDiGraph wrapper + multi-hop traversal
  extract.py        Regex + OpenAI extractors and canonical response conversion
  resolve.py        question text → entities named in the graph
  trace.py          question → trace, with designed non-found states
  storage.py        SQLite persistence (save_graph / load_graph)
tests/              — 143 tests
.github/workflows/
  ci.yml            — pytest + eval schema validation on push/PR
```

Not yet built (remaining Weeks 4–6): vector-seeded entity discovery, the first
KG eval score, demo video, and public corpus.

## API

- `GET /api/health`
- `GET /api/documents`
- `POST /api/upload` with multipart field `files`
- `GET /api/google-drive/status`
- `GET /api/google-drive/connect`
- `GET /api/google-drive/callback`
- `DELETE /api/google-drive/connection`
- `GET /api/google-drive/documents`
- `POST /api/google-drive/import` with JSON `{ "document_ids": ["..."] }`
- `POST /api/query` with JSON `{ "question": "...", "top_k": 6 }` — returns
  `{ answer, sources, mode, trace }`, where `trace` is derived from `question`.
  When a bounded graph path is found, relation-provenance chunks are
  prioritized in `sources`, deduplicated against vector/FTS results, and
  capped at `top_k`; otherwise retrieval falls back unchanged.
  Trace path nodes include `id`, `kind`, `name`, `aliases`, and `attrs`;
  relation provenance uses chunk IDs, which the UI uses to label which sources
  support graph nodes or edges.
- `GET /api/labgraph/stats`
- `GET /api/labgraph/entities?kind=method`
- `POST /api/labgraph/query-trace` with either `{ "question": "..." }` or an
  explicit `{ "source_id": "...", "target_id": "..." }` pair.
