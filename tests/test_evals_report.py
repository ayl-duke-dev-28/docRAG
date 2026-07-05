import json

import pytest

from evals.report import render_json, render_markdown
from evals.schema import EvalSummary, ExpectedSource, Question, QuestionResult


def _q() -> Question:
    return Question(
        id="q1",
        question="Did the March sync produce curriculum learning?",
        expected_entities=("curriculum learning",),
        expected_sources=(ExpectedSource(filename="paper.pdf"),),
        min_distinct_sources=1,
    )


@pytest.mark.unit
def test_markdown_report_contains_pass_rate_and_status():
    passed = QuestionResult(
        question_id="q1",
        passed=True,
        matched_entities=("curriculum learning",),
        missing_entities=(),
        matched_sources=("paper.pdf",),
        missing_sources=(),
        distinct_sources=1,
    )
    summary = EvalSummary(total=1, passed=1, failed=0, results=(passed,))
    md = render_markdown(summary, {"q1": _q()}, sut_name="stub")

    assert "SUT: `stub`" in md
    assert "Pass rate: **100%**" in md
    assert "| q1 | PASS |" in md
    assert "All questions passed" in md


@pytest.mark.unit
def test_markdown_report_lists_failing_reasons():
    failed = QuestionResult(
        question_id="q1",
        passed=False,
        matched_entities=(),
        missing_entities=("curriculum learning",),
        matched_sources=(),
        missing_sources=("paper.pdf",),
        distinct_sources=0,
        reasons=("missing entities", "missing sources"),
    )
    summary = EvalSummary(total=1, passed=0, failed=1, results=(failed,))
    md = render_markdown(summary, {"q1": _q()}, sut_name="stub")

    assert "FAIL" in md
    assert "curriculum learning" in md
    assert "paper.pdf" in md


@pytest.mark.unit
def test_json_report_shape():
    result = QuestionResult(
        question_id="q1",
        passed=False,
        matched_entities=(),
        missing_entities=("x",),
        matched_sources=(),
        missing_sources=("a.pdf",),
        distinct_sources=0,
        reasons=("reason",),
    )
    summary = EvalSummary(total=1, passed=0, failed=1, results=(result,))
    payload = json.loads(render_json(summary, sut_name="stub"))

    assert payload["sut"] == "stub"
    assert payload["total"] == 1
    assert payload["failed"] == 1
    assert payload["results"][0]["question_id"] == "q1"
    assert payload["results"][0]["missing_entities"] == ["x"]
