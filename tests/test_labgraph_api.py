from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind, Relation, RelationKind
from labgraph.storage import load_graph, save_graph


def _seed_graph() -> LabGraph:
    graph = LabGraph()
    graph.add_entity(
        Entity(id="person:alex-liu", kind=EntityKind.PERSON, name="Alex Liu")
    )
    graph.add_entity(
        Entity(
            id="paper:training-stability-2024",
            kind=EntityKind.PAPER,
            name="training_stability_2024",
            attrs=(("source_filename", "training_stability_2024.pdf"),),
        )
    )
    graph.add_entity(
        Entity(
            id="method:curriculum-learning",
            kind=EntityKind.METHOD,
            name="curriculum learning",
        )
    )
    graph.add_entity(
        Entity(
            id="decision:march-team-sync",
            kind=EntityKind.DECISION,
            name="March team sync",
        )
    )
    graph.add_relation(
        Relation(
            source_id="person:alex-liu",
            target_id="paper:training-stability-2024",
            kind=RelationKind.AUTHORED,
            provenance=("1",),
        )
    )
    graph.add_relation(
        Relation(
            source_id="paper:training-stability-2024",
            target_id="method:curriculum-learning",
            kind=RelationKind.USES_METHOD,
            provenance=("1",),
        )
    )
    graph.add_relation(
        Relation(
            source_id="method:curriculum-learning",
            target_id="decision:march-team-sync",
            kind=RelationKind.DECIDED_IN,
            provenance=("2",),
        )
    )
    return graph


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
        {"id": "person:alex-liu", "kind": "person", "name": "Alex Liu"},
        {
            "id": "paper:training-stability-2024",
            "kind": "paper",
            "name": "training_stability_2024",
        },
        {
            "id": "method:curriculum-learning",
            "kind": "method",
            "name": "curriculum learning",
        },
        {
            "id": "decision:march-team-sync",
            "kind": "decision",
            "name": "March team sync",
        },
    ]


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
