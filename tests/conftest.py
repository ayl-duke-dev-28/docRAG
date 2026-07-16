import pytest

from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind, Relation, RelationKind


def build_seed_graph() -> LabGraph:
    """The canonical demo graph: Alex Liu -> paper -> method -> decision.

    Mirrors the multi-hop path the README advertises, so tests exercise the
    same shape the product promises.
    """
    graph = LabGraph()
    graph.add_entity(Entity(id="person:alex-liu", kind=EntityKind.PERSON, name="Alex Liu"))
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
        Entity(id="decision:march-team-sync", kind=EntityKind.DECISION, name="March team sync")
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


@pytest.fixture
def seed_graph() -> LabGraph:
    return build_seed_graph()
