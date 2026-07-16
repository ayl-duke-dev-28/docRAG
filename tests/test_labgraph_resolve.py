import pytest

from labgraph.graph import LabGraph
from labgraph.resolve import resolve_mentions
from labgraph.schema import Entity, EntityKind


@pytest.mark.unit
def test_resolves_entity_named_in_question(seed_graph: LabGraph):
    # Arrange
    question = "What did Alex Liu work on?"

    # Act
    matched = resolve_mentions(seed_graph, question)

    # Assert
    assert [entity.id for entity in matched] == ["person:alex-liu"]


@pytest.mark.unit
def test_resolves_multiple_entities_and_is_case_insensitive(seed_graph: LabGraph):
    # Arrange
    question = "Which methods came out of the MARCH TEAM SYNC, per alex liu?"

    # Act
    matched = resolve_mentions(seed_graph, question)

    # Assert
    assert [entity.id for entity in matched] == [
        "decision:march-team-sync",
        "person:alex-liu",
    ]


@pytest.mark.unit
def test_ignores_punctuation_between_name_tokens(seed_graph: LabGraph):
    # Arrange
    question = "Did curriculum-learning get decided in the March team sync?"

    # Act
    matched = resolve_mentions(seed_graph, question)

    # Assert
    assert [entity.id for entity in matched] == [
        "decision:march-team-sync",
        "method:curriculum-learning",
    ]


@pytest.mark.unit
def test_returns_empty_when_question_names_nothing_in_the_graph(seed_graph: LabGraph):
    # Arrange
    question = "What is the capital of France?"

    # Act
    matched = resolve_mentions(seed_graph, question)

    # Assert
    assert matched == ()


@pytest.mark.unit
def test_does_not_match_entity_name_inside_a_larger_word():
    # Arrange: "lora" must not match the "lora" inside "floral".
    graph = LabGraph()
    graph.add_entity(Entity(id="method:lora", kind=EntityKind.METHOD, name="LoRA"))

    # Act
    matched = resolve_mentions(graph, "Describe the floral dataset.")

    # Assert
    assert matched == ()


@pytest.mark.unit
def test_matches_declared_aliases():
    # Arrange
    graph = LabGraph()
    graph.add_entity(
        Entity(
            id="person:alex-liu",
            kind=EntityKind.PERSON,
            name="Alex Liu",
            aliases=("A. Liu", "aliu@duke.edu"),
        )
    )

    # Act
    matched = resolve_mentions(graph, "Was this reviewed by A. Liu?")

    # Assert
    assert [entity.id for entity in matched] == ["person:alex-liu"]


@pytest.mark.unit
def test_matches_each_entity_once_even_when_named_repeatedly(seed_graph: LabGraph):
    # Arrange
    question = "Alex Liu, Alex Liu, and Alex Liu again."

    # Act
    matched = resolve_mentions(seed_graph, question)

    # Assert
    assert [entity.id for entity in matched] == ["person:alex-liu"]


@pytest.mark.unit
def test_returns_empty_for_blank_question(seed_graph: LabGraph):
    # Act / Assert
    assert resolve_mentions(seed_graph, "   ") == ()
