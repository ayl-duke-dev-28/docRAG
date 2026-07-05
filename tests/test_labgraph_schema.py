import pytest

from labgraph.schema import (
    Entity,
    EntityKind,
    Relation,
    RelationKind,
    canonical_id,
    normalize,
)


@pytest.mark.unit
def test_normalize_lowercases_and_slugifies():
    assert normalize("Alex Liu") == "alex-liu"
    assert normalize("  Curriculum Learning!! ") == "curriculum-learning"
    assert normalize("A.  Liu") == "a-liu"


@pytest.mark.unit
def test_normalize_handles_unicode_gracefully():
    assert normalize("") == ""
    assert normalize("---") == ""


@pytest.mark.unit
def test_canonical_id_prefixes_with_kind():
    assert canonical_id(EntityKind.PERSON, "Alex Liu") == "person:alex-liu"
    assert canonical_id(EntityKind.METHOD, "curriculum learning") == "method:curriculum-learning"


@pytest.mark.unit
def test_canonical_id_rejects_empty_name():
    with pytest.raises(ValueError, match="empty name"):
        canonical_id(EntityKind.PAPER, "")


@pytest.mark.unit
def test_entity_requires_matching_id_prefix():
    with pytest.raises(ValueError, match="must start with"):
        Entity(id="method:foo", kind=EntityKind.PERSON, name="foo")


@pytest.mark.unit
def test_entity_requires_non_empty_id_and_name():
    with pytest.raises(ValueError, match="id"):
        Entity(id="", kind=EntityKind.PERSON, name="Alex")
    with pytest.raises(ValueError, match="name"):
        Entity(id="person:alex", kind=EntityKind.PERSON, name="")


@pytest.mark.unit
def test_entity_as_attrs_dict():
    entity = Entity(
        id="paper:x",
        kind=EntityKind.PAPER,
        name="X",
        attrs=(("format", "paper"), ("year", "2024")),
    )
    assert entity.as_attrs_dict() == {"format": "paper", "year": "2024"}


@pytest.mark.unit
def test_entity_with_alias_appends_unique():
    e = Entity(id="person:alex-liu", kind=EntityKind.PERSON, name="Alex Liu")
    updated = e.with_alias("A. Liu")
    assert updated.aliases == ("A. Liu",)
    assert updated.with_alias("A. Liu").aliases == ("A. Liu",)  # dedup
    assert updated.with_alias("Alex Liu").aliases == ("A. Liu",)  # same as name


@pytest.mark.unit
def test_entity_is_immutable():
    e = Entity(id="person:alex-liu", kind=EntityKind.PERSON, name="Alex Liu")
    with pytest.raises(Exception):
        e.name = "someone else"


@pytest.mark.unit
def test_relation_rejects_self_loop():
    with pytest.raises(ValueError, match="Self-loop"):
        Relation(
            source_id="person:a",
            target_id="person:a",
            kind=RelationKind.WORKS_ON,
        )


@pytest.mark.unit
def test_relation_stores_provenance():
    rel = Relation(
        source_id="person:alex",
        target_id="paper:x",
        kind=RelationKind.AUTHORED,
        provenance=("chunk-1", "chunk-2"),
    )
    assert rel.provenance == ("chunk-1", "chunk-2")
