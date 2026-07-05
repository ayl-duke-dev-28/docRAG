import json
from pathlib import Path

import pytest

from evals.runner import main, run_eval
from evals.schema import Answer, ExpectedSource, Question
from evals.sut import NullSUT, get_sut


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS = ROOT / "evals" / "questions.yaml"


class StubSUT:
    name = "stub"

    def __init__(self, answer: Answer) -> None:
        self._answer = answer

    def run(self, question: str) -> Answer:
        return self._answer


@pytest.mark.unit
def test_get_sut_null():
    assert get_sut("null").name == "null"
    assert get_sut("none").name == "null"


@pytest.mark.unit
def test_get_sut_unknown_raises():
    with pytest.raises(ValueError, match="Unknown SUT"):
        get_sut("nope")


@pytest.mark.integration
def test_run_eval_all_fail_against_null_sut():
    q = Question(
        id="q1",
        question="ignored",
        expected_entities=("something",),
        expected_sources=(ExpectedSource(filename="paper.pdf"),),
        min_distinct_sources=1,
    )
    summary = run_eval([q], NullSUT())
    assert summary.total == 1
    assert summary.failed == 1
    assert summary.passed == 0


@pytest.mark.integration
def test_run_eval_pass_with_stub_sut():
    q = Question(
        id="q1",
        question="ignored",
        expected_entities=("methane",),
        expected_sources=(
            ExpectedSource(filename="a.pdf"),
            ExpectedSource(filename="b.docx"),
        ),
        min_distinct_sources=2,
    )
    sut = StubSUT(Answer(text="talks about methane", sources=("a.pdf", "b.docx")))
    summary = run_eval([q], sut)
    assert summary.passed == 1


@pytest.mark.integration
def test_main_writes_reports(tmp_path: Path):
    md_out = tmp_path / "report.md"
    json_out = tmp_path / "report.json"

    exit_code = main(
        [
            "--questions",
            str(DEFAULT_QUESTIONS),
            "--sut",
            "null",
            "--output-md",
            str(md_out),
            "--output-json",
            str(json_out),
        ]
    )

    assert exit_code == 0
    assert md_out.exists()
    assert json_out.exists()

    payload = json.loads(json_out.read_text())
    assert payload["sut"] == "null"
    assert payload["total"] >= 1
    assert payload["passed"] == 0

    md = md_out.read_text()
    assert "Eval report" in md
    assert "SUT: `null`" in md


@pytest.mark.integration
def test_main_returns_nonzero_when_below_threshold(tmp_path: Path):
    exit_code = main(
        [
            "--questions",
            str(DEFAULT_QUESTIONS),
            "--sut",
            "null",
            "--min-pass-rate",
            "0.5",
        ]
    )
    assert exit_code == 1


@pytest.mark.integration
def test_main_returns_zero_when_threshold_not_set(tmp_path: Path):
    exit_code = main(
        [
            "--questions",
            str(DEFAULT_QUESTIONS),
            "--sut",
            "null",
        ]
    )
    assert exit_code == 0
