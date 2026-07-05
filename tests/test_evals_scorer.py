import pytest

from evals.schema import Answer, ExpectedSource, Question
from evals.scorer import score


def make_question(**overrides) -> Question:
    defaults = dict(
        id="q1",
        question="Which method came from the March sync?",
        expected_entities=("curriculum learning",),
        expected_sources=(
            ExpectedSource(filename="paper.pdf", kind="paper"),
            ExpectedSource(filename="notes.docx", kind="meeting_note"),
        ),
        min_distinct_sources=2,
    )
    defaults.update(overrides)
    return Question(**defaults)


@pytest.mark.unit
def test_passes_when_everything_matches():
    q = make_question()
    a = Answer(
        text="The team adopted curriculum learning in March.",
        sources=("paper.pdf", "notes.docx"),
    )

    result = score(q, a)

    assert result.passed is True
    assert result.reasons == ()
    assert result.matched_entities == ("curriculum learning",)
    assert result.distinct_sources == 2


@pytest.mark.unit
def test_fails_when_entity_missing():
    q = make_question()
    a = Answer(
        text="Something unrelated.",
        sources=("paper.pdf", "notes.docx"),
    )

    result = score(q, a)

    assert result.passed is False
    assert "curriculum learning" in result.missing_entities
    assert any("missing entities" in r for r in result.reasons)


@pytest.mark.unit
def test_fails_when_expected_source_missing():
    q = make_question()
    a = Answer(
        text="Curriculum learning was decided.",
        sources=("paper.pdf",),
    )

    result = score(q, a)

    assert result.passed is False
    assert "notes.docx" in result.missing_sources


@pytest.mark.unit
def test_fails_multi_hop_when_only_one_distinct_source():
    q = make_question(
        expected_sources=(ExpectedSource(filename="paper.pdf"),),
        expected_entities=(),
    )
    a = Answer(text="", sources=("paper.pdf",))

    result = score(q, a)

    assert result.passed is False
    assert any("multi-hop" in r for r in result.reasons)


@pytest.mark.unit
def test_entity_match_is_case_insensitive():
    q = make_question(expected_entities=("Curriculum Learning",))
    a = Answer(
        text="the team chose CURRICULUM learning",
        sources=("paper.pdf", "notes.docx"),
    )

    result = score(q, a)

    assert result.passed is True


@pytest.mark.unit
def test_distinct_source_count_deduplicates():
    q = make_question(expected_entities=())
    a = Answer(
        text="",
        sources=("paper.pdf", "paper.pdf", "notes.docx"),
    )

    result = score(q, a)

    assert result.distinct_sources == 2


@pytest.mark.unit
def test_null_sut_answer_fails_cleanly():
    q = make_question()
    a = Answer(text="", sources=())

    result = score(q, a)

    assert result.passed is False
    assert result.distinct_sources == 0
    assert set(result.missing_sources) == {"paper.pdf", "notes.docx"}
