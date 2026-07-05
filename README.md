# docRAG → LabGraph (work in progress)

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

## Roadmap

- [x] **Week 1 — Eval harness.** Scoring infrastructure before any KG code.
- [ ] **Week 2 — Extraction + KG builder.** Fixed 5-entity, 6-relation schema.
      LLM extraction with structured outputs. NetworkX in memory, persisted to
      SQLite.
- [ ] **Week 3 — Google Drive ingestion.** OAuth flow, Docs → chunks → graph.
- [ ] **Week 4 — Graph-aware retrieval.** Hybrid vector seed + bounded BFS
      along typed edges. First real eval score against the KG.
- [ ] **Week 5 — Prompt + retrieval iteration** until eval hits **≥ 15 / 20**.
      Trace visualization in the UI.
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
pytest --cov=evals
```

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
tests/              — 32 tests, 93% coverage on evals/
```

Not yet built (Weeks 2–6): `labgraph/extract.py`, `labgraph/graph.py`,
`labgraph/retrieve.py`, `labgraph/sut.py`, and a Google Drive ingestion adapter.

## API

- `GET /api/health`
- `GET /api/documents`
- `POST /api/upload` with multipart field `files`
- `POST /api/query` with JSON `{ "question": "...", "top_k": 6 }`
