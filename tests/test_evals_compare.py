import json
from pathlib import Path

import pytest

from evals.compare import compare_reports, main


def _report(path: Path, *, sut: str, passed: int, total: int = 20) -> Path:
    path.write_text(
        json.dumps(
            {
                "sut": sut,
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total,
                "results": [],
            }
        )
    )
    return path


@pytest.mark.unit
def test_compare_reports_calculates_graph_improvement(tmp_path: Path):
    comparison = compare_reports(
        _report(tmp_path / "baseline.json", sut="baseline", passed=10),
        _report(tmp_path / "graph.json", sut="graph", passed=16),
    )

    assert comparison.baseline_pass_rate == 0.5
    assert comparison.graph_pass_rate == 0.8
    assert comparison.improvement == pytest.approx(0.3)


@pytest.mark.integration
def test_compare_main_enforces_graph_floor_and_no_regression(tmp_path: Path):
    baseline = _report(tmp_path / "baseline.json", sut="baseline", passed=16)
    graph = _report(tmp_path / "graph.json", sut="graph", passed=15)

    assert main([str(baseline), str(graph), "--min-graph-pass-rate", "0.75"]) == 1


@pytest.mark.integration
def test_compare_main_enforces_minimum_graph_lift(tmp_path: Path):
    baseline = _report(tmp_path / "baseline.json", sut="baseline", passed=8)
    graph = _report(tmp_path / "graph.json", sut="graph", passed=12)

    assert main(
        [
            str(baseline),
            str(graph),
            "--min-graph-pass-rate",
            "0.5",
            "--min-improvement",
            "0.3",
        ]
    ) == 1


@pytest.mark.unit
def test_compare_reports_rejects_different_question_counts(tmp_path: Path):
    baseline = _report(tmp_path / "baseline.json", sut="baseline", passed=10)
    graph = _report(tmp_path / "graph.json", sut="graph", passed=10, total=19)

    with pytest.raises(ValueError, match="same number"):
        compare_reports(baseline, graph)
