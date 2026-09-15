from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labgraph.schema import Entity, EntityKind
from labgraph.storage import save_graph
from tests.conftest import build_seed_graph as _seed_graph


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app as app_module

    graph_path = tmp_path / "labgraph.sqlite3"
    save_graph(_seed_graph(), graph_path)
    monkeypatch.setattr(app_module, "LABGRAPH_DB_PATH", graph_path, raising=False)
    return TestClient(app_module.app)


@pytest.mark.integration
def test_entity_browser_ranks_most_connected_entities_first(client: TestClient):
    # Arrange / Act
    payload = client.get("/api/labgraph/entities").json()

    # Assert
    assert payload["total"] == 4
    assert payload["returned"] == 4
    assert [(entity["name"], entity["relation_count"]) for entity in payload["entities"]] == [
        ("curriculum learning", 2),
        ("training_stability_2024", 2),
        ("Alex Liu", 1),
        ("March team sync", 1),
    ]


@pytest.mark.integration
def test_entity_browser_searches_names_case_insensitively(client: TestClient):
    payload = client.get("/api/labgraph/entities", params={"q": "ALEX"}).json()

    assert payload["total"] == 1
    assert [entity["id"] for entity in payload["entities"]] == ["person:alex-liu"]


@pytest.mark.integration
def test_entity_browser_search_matches_substrings_in_names(client: TestClient):
    payload = client.get("/api/labgraph/entities", params={"q": "stability"}).json()

    assert [entity["id"] for entity in payload["entities"]] == [
        "paper:training-stability-2024"
    ]


@pytest.mark.integration
def test_entity_browser_search_matches_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange: an entity whose alias is the only thing the query can match.
    import app as app_module

    graph = _seed_graph()
    graph.add_entity(
        Entity(
            id="method:curriculum-learning",
            kind=EntityKind.METHOD,
            name="curriculum learning",
            aliases=("scheduled sampling",),
        )
    )
    graph_path = tmp_path / "labgraph.sqlite3"
    save_graph(graph, graph_path)
    monkeypatch.setattr(app_module, "LABGRAPH_DB_PATH", graph_path, raising=False)

    # Act
    payload = (
        TestClient(app_module.app)
        .get("/api/labgraph/entities", params={"q": "scheduled"})
        .json()
    )

    # Assert
    assert [entity["id"] for entity in payload["entities"]] == [
        "method:curriculum-learning"
    ]


@pytest.mark.integration
def test_entity_browser_search_with_no_match_returns_empty_result(client: TestClient):
    payload = client.get("/api/labgraph/entities", params={"q": "nothing here"}).json()

    assert payload == {"total": 0, "returned": 0, "entities": []}


@pytest.mark.integration
def test_entity_browser_limit_caps_results_but_reports_full_total(client: TestClient):
    payload = client.get("/api/labgraph/entities", params={"limit": 2}).json()

    assert payload["total"] == 4
    assert payload["returned"] == 2
    assert len(payload["entities"]) == 2


@pytest.mark.integration
def test_entity_browser_clamps_out_of_range_limits(client: TestClient):
    assert client.get("/api/labgraph/entities", params={"limit": 0}).json()["returned"] == 1
    assert client.get("/api/labgraph/entities", params={"limit": 9999}).json()["returned"] == 4


@pytest.mark.integration
def test_entity_browser_rejects_unknown_kind(client: TestClient):
    response = client.get("/api/labgraph/entities", params={"kind": "grant"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown entity kind."


@pytest.mark.integration
def test_entity_browser_combines_kind_filter_and_search(client: TestClient):
    payload = client.get(
        "/api/labgraph/entities", params={"kind": "person", "q": "curriculum"}
    ).json()

    assert payload == {"total": 0, "returned": 0, "entities": []}
