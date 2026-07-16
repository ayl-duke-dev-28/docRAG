import pytest

from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind, Relation, RelationKind
from labgraph.trace import TraceStatus, trace_for_question


@pytest.mark.unit
def test_finds_path_between_two_entities_named_in_the_question(seed_graph: LabGraph):
    # Arrange
    question = "Which method did Alex Liu contribute that reached the March team sync?"

    # Act
    result = trace_for_question(seed_graph, question, max_depth=4)

    # Assert
    assert result.status is TraceStatus.FOUND
    assert [entity.id for entity in result.path] == [
        "person:alex-liu",
        "paper:training-stability-2024",
        "method:curriculum-learning",
        "decision:march-team-sync",
    ]


@pytest.mark.unit
def test_found_path_carries_the_relation_between_each_pair(seed_graph: LabGraph):
    # Act
    result = trace_for_question(seed_graph, "Alex Liu and the March team sync", max_depth=4)

    # Assert
    assert [relation.kind for relation in result.relations] == [
        RelationKind.AUTHORED,
        RelationKind.USES_METHOD,
        RelationKind.DECIDED_IN,
    ]


@pytest.mark.unit
def test_reports_no_graph_when_graph_is_empty():
    # Act
    result = trace_for_question(LabGraph(), "Alex Liu and the March team sync")

    # Assert
    assert result.status is TraceStatus.NO_GRAPH
    assert result.path == ()


@pytest.mark.unit
def test_reports_no_entities_when_question_names_nothing_in_the_graph(seed_graph: LabGraph):
    # Act
    result = trace_for_question(seed_graph, "What is the capital of France?")

    # Assert
    assert result.status is TraceStatus.NO_ENTITIES
    assert result.matched == ()
    assert result.path == ()


@pytest.mark.unit
def test_reports_partial_with_neighborhood_when_only_one_entity_is_named(
    seed_graph: LabGraph,
):
    # Arrange: one endpoint is not enough to form a path.
    question = "Tell me about Alex Liu."

    # Act
    result = trace_for_question(seed_graph, question, max_depth=4)

    # Assert
    assert result.status is TraceStatus.PARTIAL
    assert [entity.id for entity in result.matched] == ["person:alex-liu"]
    assert result.path == ()
    assert "paper:training-stability-2024" in {e.id for e in result.neighborhood}


@pytest.mark.unit
def test_partial_neighborhood_includes_inbound_neighbours_of_a_sink_entity(
    seed_graph: LabGraph,
):
    # Arrange: a decision has no outbound edges. Its useful context is the
    # method that was decided in it, which is inbound.
    question = "Tell me about the March team sync."

    # Act
    result = trace_for_question(seed_graph, question, max_depth=4)

    # Assert
    assert result.status is TraceStatus.PARTIAL
    assert "method:curriculum-learning" in {entity.id for entity in result.neighborhood}


@pytest.mark.unit
def test_reports_no_path_when_named_entities_are_not_connected():
    # Arrange: two entities, no edge between them.
    graph = LabGraph()
    graph.add_entity(Entity(id="person:alex-liu", kind=EntityKind.PERSON, name="Alex Liu"))
    graph.add_entity(
        Entity(id="decision:march-team-sync", kind=EntityKind.DECISION, name="March team sync")
    )

    # Act
    result = trace_for_question(graph, "Alex Liu and the March team sync", max_depth=4)

    # Assert
    assert result.status is TraceStatus.NO_PATH
    assert {entity.id for entity in result.matched} == {
        "person:alex-liu",
        "decision:march-team-sync",
    }
    assert result.path == ()
    assert result.max_depth == 4


@pytest.mark.unit
def test_reports_no_path_when_the_connection_exceeds_max_depth(seed_graph: LabGraph):
    # Arrange: the real path is 3 hops; allow only 1.
    question = "Alex Liu and the March team sync"

    # Act
    result = trace_for_question(seed_graph, question, max_depth=1)

    # Assert
    assert result.status is TraceStatus.NO_PATH
    assert result.max_depth == 1


@pytest.mark.unit
def test_prefers_the_path_covering_the_most_named_entities(seed_graph: LabGraph):
    # Arrange: names three entities. The method->decision path (2 nodes) covers
    # two of them; the person->decision path (4 nodes) covers all three.
    question = "Did Alex Liu's curriculum learning come from the March team sync?"

    # Act
    result = trace_for_question(seed_graph, question, max_depth=4)

    # Assert
    assert result.status is TraceStatus.FOUND
    assert [entity.id for entity in result.path] == [
        "person:alex-liu",
        "paper:training-stability-2024",
        "method:curriculum-learning",
        "decision:march-team-sync",
    ]


@pytest.mark.unit
def test_traverses_regardless_of_which_endpoint_the_question_names_first(
    seed_graph: LabGraph,
):
    # Arrange: the graph edge runs person -> ... -> decision, but the question
    # names the decision first. Mention order must not decide traversal order.
    question = "The March team sync — what did Alex Liu have to do with it?"

    # Act
    result = trace_for_question(seed_graph, question, max_depth=4)

    # Assert
    assert result.status is TraceStatus.FOUND
    assert result.path[0].id == "person:alex-liu"
    assert result.path[-1].id == "decision:march-team-sync"


@pytest.mark.unit
def test_reports_no_entities_for_blank_question(seed_graph: LabGraph):
    # Act
    result = trace_for_question(seed_graph, "   ")

    # Assert
    assert result.status is TraceStatus.NO_ENTITIES
