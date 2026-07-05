import pytest

from evals.schema import EvalSummary, ExpectedSource, Question, QuestionResult


@pytest.mark.unit
def test_question_requires_non_empty_id():
    with pytest.raises(ValueError, match="id"):
        Question(
            id="",
            question="q",
            expected_entities=(),
            expected_sources=(ExpectedSource(filename="a.pdf"),),
        )


@pytest.mark.unit
def test_question_requires_non_empty_text():
    with pytest.raises(ValueError, match="question"):
        Question(
            id="q1",
            question="",
            expected_entities=(),
            expected_sources=(ExpectedSource(filename="a.pdf"),),
        )


@pytest.mark.unit
def test_question_rejects_zero_distinct_sources():
    with pytest.raises(ValueError, match="min_distinct_sources"):
        Question(
            id="q1",
            question="q",
            expected_entities=(),
            expected_sources=(ExpectedSource(filename="a.pdf"),),
            min_distinct_sources=0,
        )


@pytest.mark.unit
def test_expected_source_defaults_to_unspecified_kind():
    source = ExpectedSource(filename="a.pdf")
    assert source.kind == "unspecified"


@pytest.mark.unit
def test_question_is_immutable():
    q = Question(
        id="q1",
        question="q",
        expected_entities=("x",),
        expected_sources=(ExpectedSource(filename="a.pdf"),),
    )
    with pytest.raises(Exception):
        q.id = "q2"  # frozen dataclass


@pytest.mark.unit
def test_eval_summary_pass_rate_handles_zero():
    summary = EvalSummary(total=0, passed=0, failed=0)
    assert summary.pass_rate == 0.0


@pytest.mark.unit
def test_eval_summary_pass_rate():
    result = QuestionResult(
        question_id="q1",
        passed=True,
        matched_entities=(),
        missing_entities=(),
        matched_sources=(),
        missing_sources=(),
        distinct_sources=0,
    )
    summary = EvalSummary(total=4, passed=3, failed=1, results=(result,))
    assert summary.pass_rate == 0.75
