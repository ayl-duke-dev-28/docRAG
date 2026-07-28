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
