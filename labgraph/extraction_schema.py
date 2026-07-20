"""Strict response models for LLM-backed graph extraction.

These models describe the JSON payload returned by a structured-output model.
They intentionally stay separate from the canonical graph dataclasses: entity
keys are local references within one model response and are canonicalized only
after extraction.
"""

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .schema import EntityKind, RelationKind


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _StrictResponseModel(BaseModel):
    """Base configuration compatible with OpenAI strict structured outputs."""

    model_config = ConfigDict(extra="forbid")


class ExtractionAttribute(_StrictResponseModel):
    """One string metadata value attached to an extracted graph item."""

    key: NonEmptyString
    value: str


class ExtractionEntity(_StrictResponseModel):
    """An entity mention before alias resolution and canonicalization."""

    key: NonEmptyString = Field(
        description="Unique local identifier used by relations in this response."
    )
    kind: EntityKind
    name: NonEmptyString
    aliases: list[NonEmptyString]
    attributes: list[ExtractionAttribute]


class ExtractionRelation(_StrictResponseModel):
    """A typed directed edge referencing local entity keys."""

    source_key: NonEmptyString
    target_key: NonEmptyString
    kind: RelationKind
    attributes: list[ExtractionAttribute]


class StructuredExtraction(_StrictResponseModel):
    """Complete structured-output contract for one document chunk."""

    entities: list[ExtractionEntity]
    relations: list[ExtractionRelation]

    _ENDPOINT_KINDS: ClassVar[
        dict[RelationKind, tuple[frozenset[EntityKind], frozenset[EntityKind]]]
    ] = {
        RelationKind.AUTHORED: (
            frozenset({EntityKind.PERSON}),
            frozenset({EntityKind.PAPER}),
        ),
        RelationKind.MENTIONS: (
            frozenset({EntityKind.PAPER, EntityKind.DECISION}),
            frozenset(EntityKind),
        ),
        RelationKind.USES_METHOD: (
            frozenset({EntityKind.PAPER, EntityKind.PROJECT}),
            frozenset({EntityKind.METHOD}),
        ),
        RelationKind.SUPERSEDES: (
            frozenset({EntityKind.METHOD}),
            frozenset({EntityKind.METHOD}),
        ),
        RelationKind.DECIDED_IN: (
            frozenset({EntityKind.METHOD, EntityKind.PROJECT}),
            frozenset({EntityKind.DECISION}),
        ),
        RelationKind.WORKS_ON: (
            frozenset({EntityKind.PERSON}),
            frozenset({EntityKind.PROJECT}),
        ),
    }

    _ENDPOINT_DESCRIPTIONS: ClassVar[dict[RelationKind, str]] = {
        RelationKind.AUTHORED: "person -> paper",
        RelationKind.MENTIONS: "paper|decision -> any entity",
        RelationKind.USES_METHOD: "paper|project -> method",
        RelationKind.SUPERSEDES: "method -> method",
        RelationKind.DECIDED_IN: "method|project -> decision",
        RelationKind.WORKS_ON: "person -> project",
    }

    @model_validator(mode="after")
    def validate_graph_fragment(self) -> "StructuredExtraction":
        entities_by_key = {entity.key: entity for entity in self.entities}
        if len(entities_by_key) != len(self.entities):
            raise ValueError("Entity keys must be unique within an extraction")

        for relation in self.relations:
            source = entities_by_key.get(relation.source_key)
            target = entities_by_key.get(relation.target_key)
            if source is None:
                raise ValueError(
                    f"Relation references unknown entity key {relation.source_key!r}"
                )
            if target is None:
                raise ValueError(
                    f"Relation references unknown entity key {relation.target_key!r}"
                )
            if source.key == target.key:
                raise ValueError("Self-loop relations are not allowed")

            allowed_sources, allowed_targets = self._ENDPOINT_KINDS[relation.kind]
            if source.kind not in allowed_sources or target.kind not in allowed_targets:
                expected = self._ENDPOINT_DESCRIPTIONS[relation.kind]
                raise ValueError(f"{relation.kind.value} requires {expected}")

        return self


__all__ = [
    "ExtractionAttribute",
    "ExtractionEntity",
    "ExtractionRelation",
    "StructuredExtraction",
]
