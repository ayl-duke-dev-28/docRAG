from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labgraph.extract import RegexExtractor
from labgraph.storage import load_graph, save_graph
from tests.conftest import build_seed_graph as _seed_graph


@pytest.mark.integration
def test_labgraph_stats_and_entities_endpoints_return_persisted_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import app as app_module

    graph_path = tmp_path / "labgraph.sqlite3"
    save_graph(_seed_graph(), graph_path)
    monkeypatch.setattr(app_module, "LABGRAPH_DB_PATH", graph_path, raising=False)

    client = TestClient(app_module.app)

    stats = client.get("/api/labgraph/stats")
    assert stats.status_code == 200
    assert stats.json() == {
        "status": "ok",
        "entities": 4,
        "relations": 3,
        "entity_kinds": {
            "decision": 1,
            "method": 1,
            "paper": 1,
            "person": 1,
            "project": 0,
        },
    }

    entities = client.get("/api/labgraph/entities", params={"kind": "method"})
    assert entities.status_code == 200
    assert entities.json() == [
        {
            "id": "method:curriculum-learning",
            "kind": "method",
            "name": "curriculum learning",
            "aliases": [],
            "attrs": {},
        }
    ]


@pytest.mark.integration
def test_labgraph_query_trace_endpoint_returns_readable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import app as app_module

    graph_path = tmp_path / "labgraph.sqlite3"
    save_graph(_seed_graph(), graph_path)
    monkeypatch.setattr(app_module, "LABGRAPH_DB_PATH", graph_path, raising=False)

    client = TestClient(app_module.app)
    response = client.post(
        "/api/labgraph/query-trace",
        json={
            "source_id": "person:alex-liu",
            "target_id": "decision:march-team-sync",
            "max_depth": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["trace"] == [
        "Alex Liu",
        "training_stability_2024",
        "curriculum learning",
        "March team sync",
    ]
    assert payload["path"] == [
        {
            "id": "person:alex-liu",
            "kind": "person",
            "name": "Alex Liu",
            "aliases": [],
            "attrs": {},
        },
        {
            "id": "paper:training-stability-2024",
            "kind": "paper",
            "name": "training_stability_2024",
            "aliases": [],
            "attrs": {"source_filename": "training_stability_2024.pdf"},
        },
        {
            "id": "method:curriculum-learning",
            "kind": "method",
            "name": "curriculum learning",
            "aliases": [],
            "attrs": {},
        },
        {
            "id": "decision:march-team-sync",
            "kind": "decision",
            "name": "March team sync",
            "aliases": [],
            "attrs": {},
        },
    ]
    assert payload["relations"] == [
        {
            "source_id": "person:alex-liu",
            "target_id": "paper:training-stability-2024",
            "kind": "authored",
            "provenance": ["1"],
            "attrs": {},
        },
        {
            "source_id": "paper:training-stability-2024",
            "target_id": "method:curriculum-learning",
            "kind": "uses_method",
            "provenance": ["1"],
            "attrs": {},
        },
        {
            "source_id": "method:curriculum-learning",
            "target_id": "decision:march-team-sync",
            "kind": "decided_in",
            "provenance": ["2"],
            "attrs": {},
        },
    ]


def _client_with_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient whose graph is the seeded demo graph and whose retrieval is stubbed."""
    import app as app_module

    graph_path = tmp_path / "labgraph.sqlite3"
    save_graph(_seed_graph(), graph_path)
    monkeypatch.setattr(app_module, "LABGRAPH_DB_PATH", graph_path, raising=False)
    monkeypatch.setattr(
        app_module,
        "answer",
        lambda question, top_k: {"answer": "stub answer", "sources": [], "mode": "none"},
    )
    return TestClient(app_module.app)


@pytest.mark.integration
def test_query_endpoint_returns_a_trace_derived_from_the_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    client = _client_with_graph(tmp_path, monkeypatch)

    # Act
    response = client.post(
        "/api/query",
        json={"question": "What did Alex Liu contribute to the March team sync?"},
    )

    # Assert
    assert response.status_code == 200
    trace = response.json()["trace"]
    assert trace["status"] == "found"
    assert [node["name"] for node in trace["path"]] == [
        "Alex Liu",
        "training_stability_2024",
        "curriculum learning",
        "March team sync",
    ]
    assert [relation["kind"] for relation in trace["relations"]] == [
        "authored",
        "uses_method",
        "decided_in",
    ]


@pytest.mark.integration
def test_query_endpoint_returns_no_trace_for_a_question_unrelated_to_the_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange: the regression guard. This used to return the first
    # person->decision path in the graph regardless of what was asked.
    client = _client_with_graph(tmp_path, monkeypatch)

    # Act
    response = client.post("/api/query", json={"question": "What is the capital of France?"})

    # Assert
    payload = response.json()
    assert payload["answer"] == "stub answer"
    assert payload["trace"]["status"] == "no_entities"
    assert payload["trace"]["path"] == []


@pytest.mark.integration
def test_query_endpoint_keeps_the_answer_when_the_graph_trace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    import app as app_module

    client = _client_with_graph(tmp_path, monkeypatch)
    monkeypatch.setattr(
        app_module,
        "load_graph",
        lambda path: (_ for _ in ()).throw(RuntimeError("graph is corrupt")),
    )

    # Act
    response = client.post("/api/query", json={"question": "Alex Liu and the March team sync"})

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "stub answer"
    assert payload["trace"]["status"] == "error"


@pytest.mark.integration
def test_query_trace_endpoint_accepts_a_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    client = _client_with_graph(tmp_path, monkeypatch)

    # Act
    response = client.post(
        "/api/labgraph/query-trace",
        json={"question": "Alex Liu and the March team sync"},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "found"


@pytest.mark.integration
def test_query_trace_endpoint_rejects_a_request_with_no_question_or_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    client = _client_with_graph(tmp_path, monkeypatch)

    # Act
    response = client.post("/api/labgraph/query-trace", json={"max_depth": 4})

    # Assert
    assert response.status_code == 400


@pytest.mark.integration
def test_txt_ingestion_updates_labgraph_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import docrag.ingest as ingest_module
    import docrag.storage as storage_module

    docrag_path = tmp_path / "docrag.sqlite3"
    graph_path = tmp_path / "labgraph.sqlite3"
    uploads_path = tmp_path / "uploads"
    uploads_path.mkdir()

    monkeypatch.setattr(storage_module, "DB_PATH", docrag_path)
    monkeypatch.setattr(ingest_module, "UPLOAD_DIR", uploads_path)
    monkeypatch.setattr(ingest_module, "LABGRAPH_DB_PATH", graph_path, raising=False)
    monkeypatch.setattr(ingest_module, "embed_texts", lambda texts: [])
    monkeypatch.setattr(
        ingest_module,
        "build_labgraph_extractor",
        lambda: RegexExtractor(),
    )
    storage_module.init_db()

    source = tmp_path / "note.txt"
    source.write_text(
        "Alex Liu introduced curriculum learning. "
        "We decided in the March team sync to use curriculum learning."
    )

    result = ingest_module.ingest_file(source, "training_stability_2024.txt")

    assert result["status"] == "ingested"
    graph = load_graph(graph_path)
    assert graph.has_entity("person:alex-liu")
    assert graph.has_entity("method:curriculum-learning")
    assert graph.has_entity("decision:march-team-sync")
    assert graph.shortest_path(
        "person:alex-liu", "decision:march-team-sync", max_depth=4
    ) == [
        "person:alex-liu",
        "paper:training-stability-2024",
        "method:curriculum-learning",
        "decision:march-team-sync",
    ]


@pytest.mark.integration
def test_ingestion_uses_the_runtime_selected_extractor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import docrag.ingest as ingest_module
    import docrag.storage as storage_module

    docrag_path = tmp_path / "docrag.sqlite3"
    graph_path = tmp_path / "labgraph.sqlite3"
    uploads_path = tmp_path / "uploads"
    uploads_path.mkdir()
    selected = []

    def select_extractor():
        selected.append(True)
        return RegexExtractor()

    monkeypatch.setattr(storage_module, "DB_PATH", docrag_path)
    monkeypatch.setattr(ingest_module, "UPLOAD_DIR", uploads_path)
    monkeypatch.setattr(ingest_module, "LABGRAPH_DB_PATH", graph_path, raising=False)
    monkeypatch.setattr(ingest_module, "embed_texts", lambda texts: [])
    monkeypatch.setattr(ingest_module, "build_labgraph_extractor", select_extractor)
    storage_module.init_db()

    source = tmp_path / "note.txt"
    source.write_text("Alex Liu introduced curriculum learning.")

    ingest_module.ingest_file(source, "training_stability_2024.txt")

    assert selected == [True]


@pytest.mark.integration
def test_ingestion_rolls_back_when_graph_extraction_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import docrag.ingest as ingest_module
    import docrag.storage as storage_module
    from labgraph.extract import OpenAIExtractionError

    class FailingExtractor:
        name = "openai"

        def extract(self, chunk):
            raise OpenAIExtractionError("request failed")

    docrag_path = tmp_path / "docrag.sqlite3"
    graph_path = tmp_path / "labgraph.sqlite3"
    uploads_path = tmp_path / "uploads"
    uploads_path.mkdir()

    monkeypatch.setattr(storage_module, "DB_PATH", docrag_path)
    monkeypatch.setattr(ingest_module, "UPLOAD_DIR", uploads_path)
    monkeypatch.setattr(ingest_module, "LABGRAPH_DB_PATH", graph_path, raising=False)
    monkeypatch.setattr(ingest_module, "embed_texts", lambda texts: [])
    monkeypatch.setattr(
        ingest_module,
        "build_labgraph_extractor",
        lambda: FailingExtractor(),
    )
    storage_module.init_db()

    source = tmp_path / "note.txt"
    source.write_text("Alex Liu introduced curriculum learning.")

    with pytest.raises(ValueError, match="Graph extraction failed"):
        ingest_module.ingest_file(source, "training_stability_2024.txt")

    assert storage_module.list_documents() == []
    assert list(uploads_path.iterdir()) == []
