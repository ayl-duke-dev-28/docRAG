from pathlib import Path

import pytest

from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind, Relation, RelationKind
from labgraph.storage import init_db, load_graph, save_graph


def _seed_graph() -> LabGraph:
    g = LabGraph()
    g.add_entity(
        Entity(
            id="person:alex-liu",
            kind=EntityKind.PERSON,
            name="Alex Liu",
            aliases=("A. Liu",),
            attrs=(("email", "aliu@duke.edu"),),
        )
    )
    g.add_entity(
        Entity(
            id="paper:training-stability-2024",
            kind=EntityKind.PAPER,
            name="training_stability_2024",
            attrs=(("format", "paper"), ("source_filename", "training_stability_2024.pdf")),
        )
    )
    g.add_relation(
        Relation(
            source_id="person:alex-liu",
            target_id="paper:training-stability-2024",
            kind=RelationKind.AUTHORED,
            provenance=("c1",),
        )
    )
    return g


@pytest.mark.integration
def test_save_and_load_round_trip(tmp_path: Path):
    db_path = tmp_path / "labgraph.sqlite"
    original = _seed_graph()

    save_graph(original, db_path)
    reloaded = load_graph(db_path)

    assert reloaded.entity_count == original.entity_count
    assert reloaded.relation_count == original.relation_count

    person = reloaded.get_entity("person:alex-liu")
    assert person is not None
    assert person.aliases == ("A. Liu",)
    assert person.as_attrs_dict()["email"] == "aliu@duke.edu"

    paper = reloaded.get_entity("paper:training-stability-2024")
    assert paper.as_attrs_dict()["format"] == "paper"

    relations = list(reloaded.relations(kind=RelationKind.AUTHORED))
    assert len(relations) == 1
    assert relations[0].provenance == ("c1",)


@pytest.mark.integration
def test_save_is_idempotent_when_called_twice(tmp_path: Path):
    db_path = tmp_path / "labgraph.sqlite"
    save_graph(_seed_graph(), db_path)
    save_graph(_seed_graph(), db_path)
    reloaded = load_graph(db_path)
    assert reloaded.entity_count == 2
    assert reloaded.relation_count == 1


@pytest.mark.integration
def test_load_missing_db_returns_empty_graph(tmp_path: Path):
    reloaded = load_graph(tmp_path / "nope.sqlite")
    assert reloaded.entity_count == 0
    assert reloaded.relation_count == 0


@pytest.mark.integration
def test_init_db_creates_tables(tmp_path: Path):
    import sqlite3

    db_path = tmp_path / "labgraph.sqlite"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "labgraph_entities" in tables
    assert "labgraph_relations" in tables
