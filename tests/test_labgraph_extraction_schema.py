import pytest
from pydantic import ValidationError

from labgraph.extraction_schema import (
    ExtractionAttribute,
    ExtractionEntity,
    ExtractionRelation,
    StructuredExtraction,
)
from labgraph.schema import EntityKind, RelationKind


@pytest.mark.unit
def test_structured_extraction_accepts_a_complete_graph_fragment():
    extraction = StructuredExtraction(
        entities=[
            ExtractionEntity(
                key="author",
                kind=EntityKind.PERSON,
                name="Alex Liu",
                aliases=["A. Liu"],
                attributes=[ExtractionAttribute(key="email", value="aliu@example.edu")],
            ),
            ExtractionEntity(
                key="paper",
                kind=EntityKind.PAPER,
                name="Training Stability",
                aliases=[],
                attributes=[],
            ),
        ],
        relations=[
            ExtractionRelation(
                source_key="author",
                target_key="paper",
                kind=RelationKind.AUTHORED,
                attributes=[],
            )
        ],
    )

    assert extraction.relations[0].source_key == "author"
    assert extraction.entities[0].kind is EntityKind.PERSON


@pytest.mark.unit
def test_structured_extraction_accepts_an_empty_result():
    extraction = StructuredExtraction(entities=[], relations=[])

    assert extraction.entities == []
    assert extraction.relations == []


@pytest.mark.unit
def test_structured_extraction_rejects_unknown_entity_and_relation_kinds():
    with pytest.raises(ValidationError):
        ExtractionEntity(
            key="dataset",
            kind="dataset",
            name="Benchmark",
            aliases=[],
            attributes=[],
        )

    with pytest.raises(ValidationError):
        ExtractionRelation(
            source_key="paper",
            target_key="dataset",
            kind="evaluated_on",
            attributes=[],
        )


@pytest.mark.unit
def test_structured_extraction_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ExtractionAttribute(key="year", value="2024", confidence=0.9)


@pytest.mark.unit
def test_structured_extraction_rejects_duplicate_or_unknown_entity_keys():
    duplicate_entities = [
        ExtractionEntity(
            key="method",
            kind=EntityKind.METHOD,
            name="Curriculum learning",
            aliases=[],
            attributes=[],
        ),
        ExtractionEntity(
            key="method",
            kind=EntityKind.METHOD,
            name="Gradient clipping",
            aliases=[],
            attributes=[],
        ),
    ]
    with pytest.raises(ValidationError, match="unique"):
        StructuredExtraction(entities=duplicate_entities, relations=[])

    with pytest.raises(ValidationError, match="unknown entity key"):
        StructuredExtraction(
            entities=duplicate_entities[:1],
            relations=[
                ExtractionRelation(
                    source_key="method",
                    target_key="missing",
                    kind=RelationKind.SUPERSEDES,
                    attributes=[],
                )
            ],
        )


@pytest.mark.unit
def test_generated_json_schema_is_strict_and_all_fields_are_required():
    schema = StructuredExtraction.model_json_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])

    for definition in schema["$defs"].values():
        if definition.get("type") != "object":
            continue
        assert definition["additionalProperties"] is False
        assert set(definition["required"]) == set(definition["properties"])
