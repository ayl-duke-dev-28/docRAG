import json
import math
import re
from typing import TYPE_CHECKING, Dict, List, Optional

from .config import TOP_K
from .llm import LLMError, answer_with_context, embed_texts
from .storage import all_embedded_chunks, get_chunk, search_fts

if TYPE_CHECKING:
    from labgraph.graph import LabGraph


FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def page_label(page_start, page_end) -> str:
    if not page_start:
        return "unknown"
    if page_start == page_end:
        return str(page_start)
    return "{start}-{end}".format(start=page_start, end=page_end)


def row_to_source(row, score: float) -> Dict:
    return {
        "chunk_id": row["id"],
        "filename": row["filename"],
        "pages": page_label(row["page_start"], row["page_end"]),
        "score": round(score, 4),
        "text": row["text"],
    }


def fts_query(question: str) -> str:
    tokens = FTS_TOKEN_RE.findall(question)
    if not tokens:
        return question
    return " OR ".join(tokens)


def retrieve(question: str, top_k: int = TOP_K) -> List[Dict]:
    try:
        query_embedding = embed_texts([question])
    except LLMError:
        query_embedding = []
    if query_embedding:
        q = query_embedding[0]
        scored = []
        for row in all_embedded_chunks():
            embedding = json.loads(row["embedding"])
            scored.append((cosine(q, embedding), row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row_to_source(row, score) for score, row in scored[:top_k]]

    try:
        rows = search_fts(fts_query(question), top_k)
    except Exception:
        rows = []

    sources = []
    for row in rows:
        # bm25 is better when lower, so invert for a readable confidence-ish score.
        score = 1.0 / (1.0 + abs(float(row["score"])))
        sources.append(row_to_source(row, score))
    return sources


def retrieve_graph_aware(
    question: str, graph: "LabGraph", top_k: int = TOP_K
) -> List[Dict]:
    """Combine baseline retrieval with evidence from the question's graph path.

    Relation provenance is ordered along the bounded path and placed before
    baseline results. Duplicate chunks are returned once. If the question does
    not resolve to a complete path, behavior stays identical to the baseline.
    """
    from labgraph.trace import TraceStatus, trace_for_question

    baseline = retrieve(question, top_k)
    trace = trace_for_question(graph, question)
    if trace.status is not TraceStatus.FOUND:
        return baseline

    sources: List[Dict] = []
    seen_chunk_ids = set()
    for relation in trace.relations:
        for raw_chunk_id in relation.provenance:
            try:
                chunk_id = int(raw_chunk_id)
                row = get_chunk(chunk_id)
            except (TypeError, ValueError):
                continue
            if row is None or chunk_id in seen_chunk_ids:
                continue
            sources.append(row_to_source(row, 1.0))
            seen_chunk_ids.add(chunk_id)

    for source_item in baseline:
        chunk_id = source_item.get("chunk_id")
        if chunk_id in seen_chunk_ids:
            continue
        sources.append(source_item)
        seen_chunk_ids.add(chunk_id)

    return sources[:top_k]


def answer(
    question: str,
    top_k: int = TOP_K,
    graph: Optional["LabGraph"] = None,
) -> Dict:
    sources = (
        retrieve_graph_aware(question, graph, top_k)
        if graph is not None
        else retrieve(question, top_k)
    )
    if not sources:
        return {
            "answer": "I could not find matching passages in the uploaded papers.",
            "sources": [],
            "mode": "none",
        }

    try:
        generated = answer_with_context(question, sources)
    except LLMError as exc:
        generated = None
        llm_error = str(exc)
    else:
        llm_error = None
    if generated:
        return {"answer": generated, "sources": sources, "mode": "rag"}

    snippets = []
    for i, source in enumerate(sources[:3], start=1):
        text = source["text"]
        if len(text) > 700:
            text = text[:700].rsplit(" ", 1)[0] + "..."
        snippets.append(
            "[{idx}] {filename}, pages {pages}: {text}".format(
                idx=i,
                filename=source["filename"],
                pages=source["pages"],
                text=text,
            )
        )
    return {
        "answer": (
            (
                llm_error
                or "No OPENAI_API_KEY is set, so I retrieved the most relevant passages instead "
                "of generating a synthesized answer."
            )
            + "\n\nRetrieved passages:\n\n"
            + "\n\n".join(snippets)
        ),
        "sources": sources,
        "mode": "retrieval",
    }


def source(chunk_id: int):
    row = get_chunk(chunk_id)
    if not row:
        return None
    return row_to_source(row, 1.0)
