import pytest

from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind, Relation, RelationKind


def _person(name: str = "Alex Liu") -> Entity:
    return Entity(id="person:alex-liu", kind=EntityKind.PERSON, name=name)


def _paper(name: str = "training_stability_2024") -> Entity:
    return Entity(
        id=f"paper:{name.replace('_', '-')}",
        kind=EntityKind.PAPER,
        name=name,
    )


def _method(name: str = "curriculum learning") -> Entity:
    return Entity(
        id="method:curriculum-learning",
        kind=EntityKind.METHOD,
        name=name,
    )


def _decision(name: str = "March team sync") -> Entity:
    return Entity(id="decision:march-team-sync", kind=EntityKind.DECISION, name=name)


@pytest.mark.unit
def test_add_entity_creates_node():
    g = LabGraph()
    g.add_entity(_person())
    assert g.entity_count == 1
    assert g.has_entity("person:alex-liu")


@pytest.mark.unit
def test_add_entity_is_idempotent_and_merges_aliases():
    g = LabGraph()
    g.add_entity(_person())
    merged = g.add_entity(
        Entity(
            id="person:alex-liu",
            kind=EntityKind.PERSON,
            name="Alex Liu",
            aliases=("A. Liu",),
        )
    )
    assert "A. Liu" in merged.aliases
    assert g.entity_count == 1


@pytest.mark.unit
def test_add_relation_requires_both_endpoints():
    g = LabGraph()
    g.add_entity(_person())
    with pytest.raises(KeyError):
        g.add_relation(
            Relation(
                source_id="person:alex-liu",
                target_id="paper:missing",
                kind=RelationKind.AUTHORED,
            )
        )


@pytest.mark.unit
def test_multiple_relation_kinds_between_same_pair_coexist():
    g = LabGraph()
    g.add_entity(_person())
    g.add_entity(
        Entity(id="project:atlas", kind=EntityKind.PROJECT, name="Project Atlas")
    )
    g.add_relation(
        Relation(
            source_id="person:alex-liu",
            target_id="project:atlas",
            kind=RelationKind.WORKS_ON,
        )
    )
    g.add_relation(
        Relation(
            source_id="person:alex-liu",
            target_id="project:atlas",
            kind=RelationKind.MENTIONS,
        )
    )
    assert g.relation_count == 2


@pytest.mark.unit
def test_neighbors_filtered_by_relation_kind():
    g = _small_graph()
    person_neighbors = g.neighbors("person:alex-liu")
    assert len(person_neighbors) == 1
    authored_only = g.neighbors("person:alex-liu", kind=RelationKind.AUTHORED)
    assert len(authored_only) == 1
    other_kind = g.neighbors("person:alex-liu", kind=RelationKind.WORKS_ON)
    assert other_kind == []


@pytest.mark.unit
def test_neighbors_on_missing_entity_returns_empty():
    g = LabGraph()
    assert g.neighbors("person:ghost") == []


@pytest.mark.unit
def test_entities_filter_by_kind():
    g = _small_graph()
    persons = list(g.entities(kind=EntityKind.PERSON))
    assert len(persons) == 1
    all_entities = list(g.entities())
    assert len(all_entities) == 4


@pytest.mark.unit
def test_relations_filter_by_kind():
    g = _small_graph()
    authored = list(g.relations(kind=RelationKind.AUTHORED))
    uses = list(g.relations(kind=RelationKind.USES_METHOD))
    assert len(authored) == 1
    assert len(uses) == 1


@pytest.mark.unit
def test_relations_between_returns_directed_edge_relations():
    g = _small_graph()

    relations = g.relations_between(
        "person:alex-liu",
        "paper:training-stability-2024",
    )

    assert [relation.kind for relation in relations] == [RelationKind.AUTHORED]
    assert g.relations_between("paper:training-stability-2024", "person:alex-liu") == []


@pytest.mark.unit
def test_shortest_path_finds_multi_hop_route():
    g = _small_graph()
    path = g.shortest_path("person:alex-liu", "decision:march-team-sync", max_depth=4)
    assert path == [
        "person:alex-liu",
        "paper:training-stability-2024",
        "method:curriculum-learning",
        "decision:march-team-sync",
    ]


@pytest.mark.unit
def test_shortest_path_returns_empty_when_beyond_depth():
    g = _small_graph()
    path = g.shortest_path("person:alex-liu", "decision:march-team-sync", max_depth=1)
    assert path == []


@pytest.mark.unit
def test_shortest_path_returns_self_when_source_equals_target():
    g = _small_graph()
    assert g.shortest_path("person:alex-liu", "person:alex-liu") == ["person:alex-liu"]


@pytest.mark.unit
def test_neighborhood_expansion_within_depth():
    g = _small_graph()
    nodes = g.neighborhood(["person:alex-liu"], max_depth=2)
    ids = {n.id for n in nodes}
    assert "paper:training-stability-2024" in ids
    assert "method:curriculum-learning" in ids
    # decision is 3 hops away, should not be in a depth-2 neighborhood
    assert "decision:march-team-sync" not in ids


@pytest.mark.unit
def test_neighborhood_ignores_missing_seeds():
    g = _small_graph()
    nodes = g.neighborhood(["person:ghost"], max_depth=2)
    assert nodes == []


@pytest.mark.unit
def test_neighborhood_follows_only_outbound_edges_by_default():
    g = _small_graph()
    # The decision is a sink: nothing is reachable by following edges forward.
    nodes = g.neighborhood(["decision:march-team-sync"], max_depth=2)
    assert {n.id for n in nodes} == {"decision:march-team-sync"}


@pytest.mark.unit
def test_undirected_neighborhood_reaches_inbound_neighbours():
    g = _small_graph()
    nodes = g.neighborhood(["decision:march-team-sync"], max_depth=1, directed=False)
    assert "method:curriculum-learning" in {n.id for n in nodes}


def _small_graph() -> LabGraph:
    g = LabGraph()
    g.add_entity(_person())
    g.add_entity(_paper())
    g.add_entity(_method())
    g.add_entity(_decision())
    g.add_relation(
        Relation(
            source_id="person:alex-liu",
            target_id="paper:training-stability-2024",
            kind=RelationKind.AUTHORED,
            provenance=("c1",),
        )
    )
    g.add_relation(
        Relation(
            source_id="paper:training-stability-2024",
            target_id="method:curriculum-learning",
            kind=RelationKind.USES_METHOD,
            provenance=("c1",),
        )
    )
    g.add_relation(
        Relation(
            source_id="method:curriculum-learning",
            target_id="decision:march-team-sync",
            kind=RelationKind.DECIDED_IN,
            provenance=("c2",),
        )
    )
    return g
