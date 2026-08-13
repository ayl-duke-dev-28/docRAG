from types import SimpleNamespace

import pytest
from openai import OpenAIError
from pydantic import ValidationError

from labgraph.aliases import AliasResolver
from labgraph.extract import (
    Chunk,
    ExtractionResult,
    OpenAIExtractionError,
    OpenAIExtractor,
    RegexExtractor,
    extract_many,
)
from labgraph.extraction_schema import (
    ExtractionAttribute,
    ExtractionEntity,
    ExtractionRelation,
    StructuredExtraction,
)
from labgraph.schema import EntityKind, RelationKind


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self, response=None, error=None):
        self.responses = FakeResponses(response=response, error=error)


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
def test_regex_extractor_does_not_treat_document_title_as_a_person():
    chunk = Chunk(
        id="c1",
        filename="training_stability_2024.md",
        text=(
            "# Training Stability 2024 Alex Liu authored this Project Atlas "
            "report using curriculum learning."
        ),
    )

    result = RegexExtractor().extract(chunk)

    assert [
        entity.id for entity in result.entities if entity.kind is EntityKind.PERSON
    ] == ["person:alex-liu"]


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
def test_openai_extractor_requests_structured_output_and_converts_graph_objects():
    parsed = StructuredExtraction(
        entities=[
            ExtractionEntity(
                key="author",
                kind=EntityKind.PERSON,
                name="A. Liu",
                aliases=["Alex Liu"],
                attributes=[ExtractionAttribute(key="role", value="author")],
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
                attributes=[ExtractionAttribute(key="evidence", value="by A. Liu")],
            )
        ],
    )
    client = FakeOpenAIClient(response=SimpleNamespace(output_parsed=parsed))
    aliases = AliasResolver()
    aliases.add(EntityKind.PERSON, "Alex Liu", ["A. Liu"])
    chunk = Chunk(
        id="chunk-7",
        filename="training_stability.pdf",
        text="Training Stability was written by A. Liu.",
    )

    result = OpenAIExtractor(
        model="gpt-4o-mini", client=client, aliases=aliases
    ).extract(chunk)

    assert {entity.id for entity in result.entities} == {
        "person:alex-liu",
        "paper:training-stability",
    }
    person = next(entity for entity in result.entities if entity.kind == EntityKind.PERSON)
    assert person.aliases == ("Alex Liu",)
    assert person.as_attrs_dict() == {
        "role": "author",
        "source_filename": "training_stability.pdf",
    }
    assert result.relations[0].source_id == "person:alex-liu"
    assert result.relations[0].target_id == "paper:training-stability"
    assert result.relations[0].provenance == ("chunk-7",)
    assert result.relations[0].as_attrs_dict() == {"evidence": "by A. Liu"}

    call = client.responses.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["text_format"] is StructuredExtraction
    assert len(call["input"]) == 2
    assert "training_stability.pdf" in call["input"][1]["content"]
    assert chunk.text in call["input"][1]["content"]


@pytest.mark.unit
def test_openai_extractor_returns_empty_result_for_empty_structured_output():
    parsed = StructuredExtraction(entities=[], relations=[])
    client = FakeOpenAIClient(response=SimpleNamespace(output_parsed=parsed))

    result = OpenAIExtractor(client=client).extract(
        Chunk(id="c1", filename="empty.txt", text="Nothing relevant.")
    )

    assert result == ExtractionResult()


@pytest.mark.unit
def test_openai_extractor_reports_model_refusal():
    refusal = SimpleNamespace(type="refusal", refusal="I cannot process this text.")
    response = SimpleNamespace(
        output_parsed=None,
        output=[SimpleNamespace(content=[refusal])],
    )

    with pytest.raises(OpenAIExtractionError, match="refused.*cannot process"):
        OpenAIExtractor(client=FakeOpenAIClient(response=response)).extract(
            Chunk(id="c1", filename="a.pdf", text="text")
        )


@pytest.mark.unit
def test_openai_extractor_rejects_response_without_parsed_output():
    response = SimpleNamespace(output_parsed=None, output=[])

    with pytest.raises(OpenAIExtractionError, match="no parsed output"):
        OpenAIExtractor(client=FakeOpenAIClient(response=response)).extract(
            Chunk(id="c1", filename="a.pdf", text="text")
        )


@pytest.mark.unit
def test_openai_extractor_wraps_openai_api_errors():
    client = FakeOpenAIClient(error=OpenAIError("service unavailable"))

    with pytest.raises(OpenAIExtractionError, match="request failed.*service unavailable"):
        OpenAIExtractor(client=client).extract(
            Chunk(id="c1", filename="a.pdf", text="text")
        )


@pytest.mark.unit
def test_openai_extractor_wraps_structured_output_validation_errors():
    with pytest.raises(ValidationError) as exc_info:
        StructuredExtraction.model_validate({"entities": []})

    client = FakeOpenAIClient(error=exc_info.value)

    with pytest.raises(OpenAIExtractionError, match="invalid structured output"):
        OpenAIExtractor(client=client).extract(
            Chunk(id="c1", filename="a.pdf", text="text")
        )
