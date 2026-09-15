import json
from pathlib import Path

import pytest

from evals.published import PublishedReport, load_published_reports


def _write_report(directory: Path, name: str, **overrides) -> Path:
    payload = {
        "sut": "labgraph-graph-aware",
        "total": 20,
        "passed": 20,
        "failed": 0,
        "pass_rate": 1.0,
        "results": [],
        **overrides,
    }
    path = directory / f"{name}.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.mark.unit
def test_published_reports_are_summarized_without_per_question_detail(tmp_path: Path):
    # Arrange
    _write_report(tmp_path, "public-graph")

    # Act
    reports = load_published_reports(tmp_path)

    # Assert
    assert reports == [
        PublishedReport(
            name="public-graph",
            sut="labgraph-graph-aware",
            total=20,
            passed=20,
            failed=0,
            pass_rate=1.0,
        )
    ]


@pytest.mark.unit
def test_published_reports_are_ordered_by_name(tmp_path: Path):
    _write_report(tmp_path, "public-graph")
    _write_report(tmp_path, "challenge-baseline", total=5, passed=2, failed=3, pass_rate=0.4)

    assert [report.name for report in load_published_reports(tmp_path)] == [
        "challenge-baseline",
        "public-graph",
    ]


@pytest.mark.unit
def test_malformed_reports_are_skipped_rather_than_breaking_the_listing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    # Arrange: one good report beside unparseable and incomplete ones.
    _write_report(tmp_path, "public-graph")
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "partial.json").write_text(json.dumps({"sut": "x"}))

    # Act
    with caplog.at_level("WARNING"):
        reports = load_published_reports(tmp_path)

    # Assert: a display-only listing degrades instead of failing, but says so.
    assert [report.name for report in reports] == ["public-graph"]
    assert "broken.json" in caplog.text
    assert "partial.json" in caplog.text


@pytest.mark.unit
def test_missing_reports_directory_returns_no_reports(tmp_path: Path):
    assert load_published_reports(tmp_path / "absent") == []


@pytest.mark.unit
def test_checked_in_reports_load_from_the_default_directory():
    reports = load_published_reports()

    assert {report.name for report in reports} == {
        "challenge-baseline",
        "challenge-graph",
        "public-baseline",
        "public-graph",
    }
    assert all(0.0 <= report.pass_rate <= 1.0 for report in reports)
