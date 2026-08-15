import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class EvalComparison:
    baseline_pass_rate: float
    graph_pass_rate: float
    improvement: float
    total: int


def _load_report(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"total", "pass_rate"}
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Eval report {path} is missing: {', '.join(sorted(missing))}")
    return payload


def compare_reports(baseline_path: Path, graph_path: Path) -> EvalComparison:
    baseline = _load_report(baseline_path)
    graph = _load_report(graph_path)
    if baseline["total"] != graph["total"]:
        raise ValueError("Eval reports must contain the same number of questions")

    baseline_rate = float(baseline["pass_rate"])
    graph_rate = float(graph["pass_rate"])
    return EvalComparison(
        baseline_pass_rate=baseline_rate,
        graph_pass_rate=graph_rate,
        improvement=graph_rate - baseline_rate,
        total=int(graph["total"]),
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.compare",
        description="Compare baseline and graph-aware LabGraph eval reports.",
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--min-graph-pass-rate", type=float, default=0.75)
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=0.0,
        help="Minimum graph-minus-baseline pass-rate improvement.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    comparison = compare_reports(args.baseline, args.graph)
    sys.stdout.write(
        "baseline: {baseline:.0%}\ngraph: {graph:.0%}\nimprovement: {delta:+.0%}\n".format(
            baseline=comparison.baseline_pass_rate,
            graph=comparison.graph_pass_rate,
            delta=comparison.improvement,
        )
    )
    if comparison.graph_pass_rate < args.min_graph_pass_rate:
        return 1
    if comparison.improvement < args.min_improvement:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
