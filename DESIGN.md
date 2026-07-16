# LabGraph Design Specification

LabGraph is a research-lab knowledge tool, not a generic chat demo. The interface must help a lab member understand why an answer is true by showing the documents, entities, and graph path behind it.

This file is the source of truth for product design decisions. Any UI work should match it unless the change updates this file first.

## Product Promise

LabGraph answers multi-hop research questions across papers and meeting notes, then shows the graph traversal that produced the answer.

The signature user moment is:

```text
paper A -> method:curriculum-learning -> decided_in -> notes 2024-03-14
```

Users should leave each answer knowing:

- What answer the system found.
- Which files supported it.
- Which entities were connected.
- Which graph path made the answer possible.
- Whether the result came from local retrieval, LLM RAG, or graph-aware retrieval.

## Target Users

Primary users are research lab members who need to reconstruct why a method, project, or decision exists.

Design for these concrete situations:

- A PI checking which paper or note introduced a method.
- A grad student tracing a decision back to a meeting note.
- A collaborator searching across papers they did not personally write.
- A demo viewer judging whether this is meaningfully better than standard RAG.

The product should feel precise, calm, and inspectable. Avoid marketing-page patterns, decorative illustrations, generic card grids, and empty "AI assistant" language.

## Design Principles

1. The graph trace is the product. It must be more visually important than generic citations.
2. Every answer must expose evidence. Never show a polished answer without sources or an explicit "no sources found" state.
3. Typed entities matter. Person, Project, Method, Paper, and Decision should look distinct enough to scan.
4. Edge cases are first-class. No graph, no path, no documents, failed upload, duplicate upload, and local-only mode all need designed states.
5. Keep the working surface dense but readable. This is a research tool, not a landing page.
6. Prefer direct labels over clever language. Users should not have to decode product copy.
7. Accessibility is part of correctness. Keyboard use, contrast, focus states, and screen reader labels are required.

## Information Architecture

The app remains a two-region workspace on desktop:

- Left: corpus and graph context.
- Right: question, answer, trace, and sources.

On mobile, the regions stack in this order:

1. Ask box.
2. Latest answer and graph trace.
3. Sources.
4. Corpus and graph status.

The first desktop viewport must communicate four things without scrolling:

- Product identity: `LabGraph`.
- Corpus readiness: uploaded documents and graph entity/relation counts.
- Primary action: ask a research question.
- Current answer mode: local retrieval, LLM RAG, or graph-aware retrieval.

## Naming

The product name in the UI is `LabGraph`.

`docRAG` may appear only as legacy or baseline context in technical docs, import paths, backward-compatible config aliases, and the current legacy SQLite filename. The user-facing app chrome, FastAPI metadata, Docker service, smoke-test output, and new environment variables should lead with `LabGraph`.

Recommended title treatment:

- Primary: `LabGraph`
- Supporting line: `Ask research questions across papers and meeting notes. Inspect the graph path behind each answer.`

## Visual System

Use a quiet utility palette with enough semantic distinction for entity types.

Base colors:

- Background: `#eef3f1`
- Panel: `#ffffff`
- Surface: `#f8fbfa`
- Ink: `#17201b`
- Muted text: `#5f6f68`
- Border: `#d8ded9`
- Primary action: `#0f766e`
- Primary action text: `#ffffff`
- Warning or source accent: `#f4b860`
- Danger: `#8a2c2c`

Entity colors:

- Person: `#2563eb`
- Project: `#7c3aed`
- Method: `#0f766e`
- Paper: `#b45309`
- Decision: `#be123c`

Typography:

- Use Inter if available, then system sans.
- H1: 28px, 1.05 line-height, 700 weight.
- H2: 15px, 700 weight.
- Body: 14-16px depending on density.
- Metadata: 12px, muted.
- Do not use viewport-scaled type.

Shape and spacing:

- Cards and panels use 8px radius or less.
- Main workspace gap: 16px.
- Panel padding: 20-22px desktop, 14-16px mobile.
- Repeated rows use 8-12px vertical spacing.
- Avoid nested cards. Use bordered rows, sections, and inline chips instead.

## Core Screens

### Main Workspace

Required sections:

- Brand and mode indicator.
- Upload area.
- LabGraph status.
- Library search, filters, sort, and document list.
- Chat answer area.
- Query composer.

Primary hierarchy:

1. Query composer and latest answer.
2. Graph trace.
3. Sources.
4. Corpus controls.
5. Maintenance actions such as refresh, rename, and delete.

### Corpus Panel

The corpus panel answers: "What can the system currently reason over?"

Required content:

- Upload control for PDF, TXT, Markdown, and eventually Google Docs.
- Document count.
- Chunk count when available.
- Graph entity count.
- Graph relation count.
- Entity-kind counts when available.
- Search by filename.
- Filter by file type or source type.
- Sort by newest, name, pages, chunks, and graph contribution when available.

Document rows must show:

- Filename.
- Source type.
- Pages or document length.
- Chunk count.
- Ingestion status.
- Graph contribution summary when available, for example `4 methods, 2 decisions`.
- Actions: open, rename, delete.

### Query And Answer Panel

The answer panel answers: "What did the system find, and why should I trust it?"

Required answer order:

1. User question.
2. Retrieval or reasoning status while loading.
3. Final answer.
4. Graph trace.
5. Sources.
6. Diagnostics only when useful.

The answer text should be plain and source-backed. Do not over-style assistant messages as chat bubbles if that reduces scanability.

## Graph Trace Component

The graph trace is the most important UI component.

The trace must be derived from the question that produced the answer beside it.
A path the question did not ask for is not evidence, and a plausible-looking
wrong path is worse than no path at all: it invites the user to trust a
connection the system never made. When the question cannot be connected to the
graph, show the matching trace state below instead of substituting another
path.

Required behavior:

- Resolve the trace endpoints from entities named in the question.
- Show the path as ordered nodes connected by relation labels.
- Use entity-kind chips for nodes.
- Show relation labels between nodes, not just arrows.
- Preserve the original path order.
- Keep long names readable with wrapping, not truncation-only.
- Allow each node to expose kind, canonical id, aliases, and source files when data exists.
- Allow each relation to expose relation kind and provenance when data exists.

Preferred desktop layout:

```text
[Person: Alex Liu]
  authored
[Paper: Training Stability 2024]
  uses_method
[Method: Curriculum Learning]
  decided_in
[Decision: March team sync]
```

Compact inline traces are acceptable only for short paths. A path of 4+ nodes should use a stacked or stepper layout so labels remain readable.

Trace states:

- Found: show full path, relation labels, and source-backed provenance.
- No graph built: explain that documents need ingestion before graph tracing works.
- No entities in question: the question named nothing in the graph. Say so, and
  prompt the user to name two entities from their corpus. This is the most
  common state on a real corpus, so it must read as a normal outcome rather
  than a failure.
- No path found: show searched endpoints and max depth, then suggest a next action.
- Partial path: only one entity was named. Show its immediate neighborhood in
  both edge directions — a Decision has no outbound edges, and the methods
  decided in it are exactly the context worth showing — and mark the missing
  endpoint.
- Error: show a plain-language failure and preserve the answer and sources if they exist.

## Source Evidence

Sources are not footnotes. They are the audit trail.

Each source item must show:

- Citation index.
- Filename.
- Page range or chunk location.
- Relevant excerpt.
- Source type.
- Which graph node or relation it supports when available.

Sources should default collapsed after the first two. The user must be able to expand them without losing their place in the answer.

## Empty States

### No Documents

Message:

```text
Add papers or notes to build the lab graph.
```

Required action:

- Upload files.

Supporting context:

```text
PDF, TXT, and Markdown are supported now. Google Docs ingestion is planned.
```

### No Graph

Message:

```text
No graph built yet.
```

Required action:

- Upload documents or run graph extraction, depending on implementation stage.

Supporting context:

```text
LabGraph extracts people, projects, methods, papers, and decisions, then connects them with typed relations.
```

### No Query Yet

Message:

```text
Ask a question that needs more than one source.
```

Example prompt:

```text
Which published methods came out of the March team sync?
```

## Loading States

Uploading:

- Show per-file progress if available.
- Show `Indexing uploaded papers...` only as a temporary state.
- On completion, list each file and whether it was indexed, skipped as duplicate, or failed.

Querying:

- Replace generic `Searching papers...` with staged status when possible:
  - `Searching corpus`
  - `Finding graph entities`
  - `Walking typed relations`
  - `Preparing cited answer`

Graph trace:

- Do not show an empty trace container while loading.
- Show the trace region only when found, not found, partial, or errored.

## Error States

Errors must be specific and recoverable.

Upload errors:

- Unsupported type: say which file failed and list supported types.
- Duplicate: say the file is already indexed.
- Parse failure: say the file could not be read and keep other successful uploads.

Query errors:

- Empty question: keep focus in the question box.
- Retrieval failure: preserve the user question and offer retry.
- LLM unavailable: fall back to local retrieval and label the answer mode.
- Graph unavailable: still show answer and sources if retrieval succeeded.

Delete errors:

- If deletion fails, keep the row visible and show the error near the row.
- Confirm destructive deletes with the filename.

## Interaction Rules

Keyboard:

- `Tab` reaches upload, search, filters, document actions, query box, submit, source expanders, and trace details.
- `Enter` submits a single-line query only when focus is not inside a multiline text area.
- `Escape` closes dialogs or inline detail popovers.

Focus:

- Every interactive element needs a visible focus ring.
- After upload, focus returns to the library or the first failed file message.
- After submit, focus remains in the query area unless an error needs correction.

Click targets:

- Minimum touch target is 44px on mobile.
- Text-only controls are allowed for clear commands, but destructive actions must be visually distinct.

## Responsive Requirements

Desktop, 1024px and wider:

- Two-column workspace.
- Left column fixed between 300px and 380px.
- Right column takes remaining space.
- Query composer sticks to the bottom of the answer panel.

Tablet, 821px to 1023px:

- Two columns may remain if content does not crowd.
- If the graph trace becomes cramped, stack the corpus above answer.

Mobile, 820px and narrower:

- Single-column layout.
- Ask box appears before corpus controls.
- Graph trace uses stacked nodes.
- Document actions wrap without horizontal scrolling.
- Source excerpts remain readable without pinch zoom.

## Accessibility Requirements

Required:

- Semantic headings in order.
- Labels for upload, search, filters, sort, query, and buttons.
- `aria-live="polite"` for upload, query, and graph status updates.
- Contrast ratio at least 4.5:1 for normal text.
- Do not rely on color alone for entity kind. Pair color with text labels.
- All dialogs and confirmations must be keyboard reachable.
- Source expanders must use native `details`/`summary` or equivalent accessible disclosure behavior.

## Implementation Priorities

### Completed UI Foundation

Completed:

1. Rename visible app chrome from `docRAG` to `LabGraph`.
2. Update the first-screen subtitle to frame the app around research questions, meeting notes, and graph paths.
3. Update the initial assistant message and query placeholder to point users toward multi-hop questions.
4. Rename runtime-facing metadata and operational labels to `LabGraph`, including FastAPI title, Docker Compose service, smoke-test output, eval harness copy, and `.env.example` variables.
5. Keep old `DOCRAG_*` config names as backward-compatible fallbacks while making `LABGRAPH_*` the documented path.
6. Replace the current inline trace row with a dedicated ordered graph trace component with a header, numbered nodes, stacked layout, and visual connectors.
7. Enrich `/api/labgraph/query-trace` with relation metadata and render relation labels between trace nodes.
8. Derive the trace from the question. `/api/query` resolves the entities named in the question, walks between them, and returns the trace with the answer, so an answer and its trace cannot disagree.
9. Add designed states for no graph, no entities, no path, partial path, and graph error.

### Next UI Slice

Build the LabGraph answer experience before broadening ingestion.

Required changes:

1. Show entity kinds on nodes.
2. Tie sources to graph nodes or relations when provenance data exists.
3. Replace `Searching corpus...` with the staged query status named under Loading States.

### After That

1. Add an entity browser in the corpus panel.
2. Add Google Drive ingestion status and source-type filtering.
3. Add graph-aware retrieval mode labeling.
4. Add eval result visibility for the current corpus.
5. Add demo-ready sample corpus onboarding.

## Non-Goals

Do not build:

- A marketing homepage.
- A separate dashboard before the trace experience works.
- Decorative graph animations that do not improve inspection.
- A force-directed graph as the primary answer view. It can be supplementary later, but the answer trace must remain ordered and readable.
- A broad design system package before the core LabGraph UI is specified and shipped.

## Acceptance Checklist

Before shipping any LabGraph UI change:

- The first screen says `LabGraph`.
- The user can ask a multi-hop question without reading instructions.
- The latest answer shows an answer, graph trace, and sources in that order.
- The trace was derived from the question, or a trace state explains why there is none.
- The trace includes node kinds and relation labels.
- Empty states have a next action.
- Loading states name the current operation.
- Error states preserve successful partial results.
- Mobile has no horizontal scrolling.
- Keyboard navigation reaches every control.
- Long filenames and long entity names wrap cleanly.
- The UI still works without an OpenAI API key.
