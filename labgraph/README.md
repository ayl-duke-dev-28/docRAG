# labgraph — the typed knowledge graph

The KG that turns LabGraph's legacy single-source retrieval into multi-hop reasoning.

## Model

Five entity kinds, six relation kinds. Nothing else in v1.

```
Person, Project, Method, Paper, Decision
authored, mentions, uses_method, supersedes, decided_in, works_on
```

Every ingested document (papers AND meeting notes) becomes a `Paper` node in
the graph. Meeting notes surface `Decision` nodes; papers surface `Method`
nodes; the bridge between them is what powers multi-hop.

## Modules

- **`schema.py`** — enums, frozen dataclasses (`Entity`, `Relation`), and the
  canonical-id function that keeps identifiers stable across ingestions.
- **`extraction_schema.py`** — strict Pydantic response models for OpenAI
  structured outputs, including entity-key references and relation endpoint
  validation before graph canonicalization.
- **`aliases.py`** — `AliasResolver` reads `labgraph/aliases.yaml` and collapses
  surface forms ("Alex Liu", "A. Liu", "aliu@duke.edu") to a single node id.
- **`graph.py`** — `LabGraph` wraps `networkx.MultiDiGraph`, exposes
  `add_entity`, `add_relation`, `neighbors`, `neighborhood`, `shortest_path`.
  Merging is idempotent — the same entity ingested twice grows its alias set
  instead of duplicating.
- **`extract.py`** — `Extractor` protocol + `RegexExtractor` (deterministic
  baseline) + `OpenAIExtractor` (stub for the LLM slice). `extract_many`
  batches chunks.
- **`storage.py`** — `save_graph` / `load_graph` persist the graph to SQLite
  (`labgraph_entities` + `labgraph_relations` tables) so runs survive
  process restart.

## Why a regex extractor exists

CI runs on every push without an OpenAI key. The regex extractor is
deterministic, dependency-free, and slow-path-free — so tests and CI can
exercise the full pipeline (extract → build graph → traverse) without
network or token cost. The real LLM extractor lands next; both implement
the same `Extractor` protocol so callers do not care.

## Quick start

```python
from pathlib import Path
from labgraph import AliasResolver, LabGraph, RegexExtractor
from labgraph.extract import Chunk, extract_many
from labgraph.storage import save_graph, load_graph

aliases = AliasResolver.from_yaml(Path("labgraph/aliases.yaml"))
extractor = RegexExtractor(aliases=aliases)

chunks = [
    Chunk(id="c1", filename="training_stability.pdf",
          text="Alex Liu introduced curriculum learning."),
    Chunk(id="c2", filename="2024-03-14-team-sync.docx",
          text="We decided in the March team sync to use curriculum learning."),
]

result = extract_many(extractor, chunks)
graph = LabGraph()
for entity in result.entities:
    graph.add_entity(entity)
for relation in result.relations:
    graph.add_relation(relation)

save_graph(graph, Path("data/labgraph.sqlite"))
```

## Not yet built

- OpenAI extractor implementation (structured outputs)
- Google Drive ingestion adapter (Week 3)
- KG-aware retrieval + SUT (Week 4)
