import pytest

from labgraph.aliases import AliasResolver
from labgraph.extract import (
    Chunk,
    OpenAIExtractor,
    RegexExtractor,
    extract_many,
)
from labgraph.schema import EntityKind, RelationKind


@pytest.mark.unit
def test_regex_extractor_finds_paper_from_pdf_chunk():
    chunk = Chunk(
        id="c1",
        filename="training_stability_2024.pdf",
        text="Alex Liu introduced curriculum learning.",
    )
    result = RegexExtractor().extract(chunk)

    paper_ids = [e.id for e in result.entities if e.kind == EntityKind.PAPER]
    assert paper_ids == ["paper:training-stability-2024"]


@pytest.mark.unit
def test_regex_extractor_labels_meeting_note_format():
    chunk = Chunk(
        id="c2",
        filename="2024-03-14-team-sync.docx",
        text="Alex Liu presented curriculum learning.",
    )
    result = RegexExtractor().extract(chunk)
    paper = next(e for e in result.entities if e.kind == EntityKind.PAPER)
    assert paper.as_attrs_dict()["format"] == "meeting_note"


@pytest.mark.unit
def test_regex_extractor_finds_person_and_method():
    chunk = Chunk(
        id="c1",
        filename="a.pdf",
        text="Alex Liu introduced curriculum learning last week.",
    )
    result = RegexExtractor().extract(chunk)
    kinds = {e.kind for e in result.entities}
    assert EntityKind.PERSON in kinds
    assert EntityKind.METHOD in kinds


@pytest.mark.unit
def test_regex_extractor_emits_authored_and_uses_method_relations():
    chunk = Chunk(
        id="c1",
        filename="a.pdf",
        text="Alex Liu introduced curriculum learning.",
    )
    result = RegexExtractor().extract(chunk)
    kinds = {r.kind for r in result.relations}
    assert RelationKind.AUTHORED in kinds
    assert RelationKind.USES_METHOD in kinds


@pytest.mark.unit
def test_regex_extractor_emits_decided_in_when_decision_present():
    chunk = Chunk(
        id="c1",
        filename="notes.docx",
        text="We decided in the March team sync to use curriculum learning.",
    )
    result = RegexExtractor().extract(chunk)
    assert any(r.kind == RelationKind.DECIDED_IN for r in result.relations)


@pytest.mark.unit
def test_regex_extractor_uses_alias_resolver():
    aliases = AliasResolver()
    aliases.add(EntityKind.PERSON, "Alex Liu", ["Alexander Liu"])
    chunk = Chunk(
        id="c1",
        filename="a.pdf",
        text="Alexander Liu proposed curriculum learning.",
    )
    result = RegexExtractor(aliases=aliases).extract(chunk)
    person = next(e for e in result.entities if e.kind == EntityKind.PERSON)
    assert person.id == "person:alex-liu"


@pytest.mark.unit
def test_regex_extractor_handles_empty_filename():
    chunk = Chunk(id="c1", filename="", text="Alex Liu wrote something.")
    result = RegexExtractor().extract(chunk)
    assert not any(e.kind == EntityKind.PAPER for e in result.entities)


@pytest.mark.unit
def test_extract_many_deduplicates_entities():
    chunks = [
        Chunk(id="c1", filename="a.pdf", text="Alex Liu wrote curriculum learning."),
        Chunk(id="c2", filename="a.pdf", text="Alex Liu also wrote gradient clipping."),
    ]
    result = extract_many(RegexExtractor(), chunks)
    person_ids = [e.id for e in result.entities if e.kind == EntityKind.PERSON]
    assert person_ids.count("person:alex-liu") == 1


@pytest.mark.unit
def test_openai_extractor_is_stub():
    with pytest.raises(NotImplementedError):
        OpenAIExtractor().extract(Chunk(id="c1", filename="a.pdf", text="hi"))
