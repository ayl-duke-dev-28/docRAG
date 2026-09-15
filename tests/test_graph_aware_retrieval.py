from typing import Dict

import pytest

from docrag import retrieval
from tests.conftest import build_seed_graph


def _chunk(chunk_id: int, filename: str, text: str) -> Dict:
    return {
        "id": chunk_id,
        "filename": filename,
        "page_start": 1,
        "page_end": 1,
        "text": text,
    }


def test_source_payload_includes_document_source_type():
    row = _chunk(1, "team-sync.md", "Meeting notes")
    row["source_type"] = "google_drive"

    source = retrieval.row_to_source(row, 0.9)

    assert source["source_type"] == "google_drive"


def test_graph_aware_retrieval_prioritizes_path_provenance_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
):
    graph = build_seed_graph()
    rows = {
        1: _chunk(1, "training_stability_2024.pdf", "Alex authored the paper."),
        2: _chunk(2, "march-team-sync.md", "The team adopted curriculum learning."),
    }
    baseline = [
        retrieval.row_to_source(rows[1], 0.9),
        retrieval.row_to_source(
            _chunk(3, "background.pdf", "Background material."), 0.8
        ),
    ]
    monkeypatch.setattr(retrieval, "retrieve", lambda question, top_k: baseline)
    monkeypatch.setattr(retrieval, "get_chunk", lambda chunk_id: rows.get(chunk_id))

    sources = retrieval.retrieve_graph_aware(
        "What did Alex Liu contribute to the March team sync?",
        graph,
        top_k=3,
    )

    assert [source["chunk_id"] for source in sources] == [1, 2, 3]
    assert len({source["chunk_id"] for source in sources}) == len(sources)


def test_graph_aware_retrieval_keeps_baseline_for_unrelated_question(
    monkeypatch: pytest.MonkeyPatch,
):
    graph = build_seed_graph()
    baseline = [
        retrieval.row_to_source(
            _chunk(7, "geography.pdf", "Paris is the capital of France."), 0.9
        )
    ]
    monkeypatch.setattr(retrieval, "retrieve", lambda question, top_k: baseline)
    monkeypatch.setattr(
        retrieval,
        "get_chunk",
        lambda chunk_id: pytest.fail("unrelated questions must not expand graph chunks"),
    )

    sources = retrieval.retrieve_graph_aware(
        "What is the capital of France?",
        graph,
        top_k=3,
    )

    assert sources == baseline


def test_graph_aware_retrieval_uses_seed_neighborhood_without_named_path(
    monkeypatch: pytest.MonkeyPatch,
):
    graph = build_seed_graph()
    rows = {
        1: _chunk(1, "training_stability_2024.pdf", "Alex authored the paper."),
        2: _chunk(2, "march-team-sync.md", "The team adopted curriculum learning."),
        3: _chunk(3, "background.pdf", "Background material."),
    }
    baseline = [
        retrieval.row_to_source(rows[1], 0.9),
        retrieval.row_to_source(rows[3], 0.8),
    ]
    monkeypatch.setattr(retrieval, "retrieve", lambda question, top_k: baseline)
    monkeypatch.setattr(retrieval, "get_chunk", lambda chunk_id: rows.get(chunk_id))

    sources = retrieval.retrieve_graph_aware(
        "How can we improve training stability?",
        graph,
        top_k=3,
    )

    assert [source["chunk_id"] for source in sources] == [1, 2, 3]
    assert sources[1]["filename"] == "march-team-sync.md"


def test_baseline_sources_are_labelled_as_vector_retrieval():
    source = retrieval.row_to_source(_chunk(1, "paper.pdf", "Body text"), 0.9)

    assert source["retrieval"] == "vector"


def test_graph_promoted_sources_are_labelled_separately_from_baseline(
    monkeypatch: pytest.MonkeyPatch,
):
    # Arrange: chunk 2 can only reach the context through the graph.
    graph = build_seed_graph()
    rows = {
        1: _chunk(1, "training_stability_2024.pdf", "Alex authored the paper."),
        2: _chunk(2, "march-team-sync.md", "The team adopted curriculum learning."),
    }
    baseline = [retrieval.row_to_source(rows[1], 0.9)]
    monkeypatch.setattr(retrieval, "retrieve", lambda question, top_k: baseline)
    monkeypatch.setattr(retrieval, "get_chunk", lambda chunk_id: rows.get(chunk_id))

    # Act
    sources = retrieval.retrieve_graph_aware(
        "What did Alex Liu contribute to the March team sync?",
        graph,
        top_k=3,
    )

    # Assert
    labels = {source["chunk_id"]: source["retrieval"] for source in sources}
    assert labels == {1: "graph", 2: "graph"}


def test_answer_reports_graph_retrieval_mode_when_the_graph_contributed(
    monkeypatch: pytest.MonkeyPatch,
):
    graph = build_seed_graph()
    rows = {
        1: _chunk(1, "training_stability_2024.pdf", "Alex authored the paper."),
        2: _chunk(2, "march-team-sync.md", "The team adopted curriculum learning."),
    }
    monkeypatch.setattr(
        retrieval,
        "retrieve",
        lambda question, top_k: [retrieval.row_to_source(rows[1], 0.9)],
    )
    monkeypatch.setattr(retrieval, "get_chunk", lambda chunk_id: rows.get(chunk_id))
    monkeypatch.setattr(
        retrieval, "answer_with_context", lambda question, sources: None
    )

    result = retrieval.answer(
        "What did Alex Liu contribute to the March team sync?", 3, graph=graph
    )

    assert result["retrieval_mode"] == "graph"


def test_answer_reports_vector_retrieval_mode_without_a_graph(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        retrieval,
        "retrieve",
        lambda question, top_k: [
            retrieval.row_to_source(_chunk(9, "geography.pdf", "Paris."), 0.9)
        ],
    )
    monkeypatch.setattr(
        retrieval, "answer_with_context", lambda question, sources: None
    )

    result = retrieval.answer("What is the capital of France?", 3)

    assert result["retrieval_mode"] == "vector"


def test_answer_without_sources_reports_no_retrieval_mode(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(retrieval, "retrieve", lambda question, top_k: [])

    result = retrieval.answer("Nothing matches this.", 3)

    assert result["mode"] == "none"
    assert result["retrieval_mode"] == "none"
