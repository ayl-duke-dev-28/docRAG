import argparse
import sys
from pathlib import Path
from typing import Sequence, Tuple

from .loader import load_questions
from .report import render_json, render_markdown
from .schema import EvalSummary, Question, QuestionResult
from .scorer import score
from .sut import SystemUnderTest, get_sut


DEFAULT_QUESTIONS = Path("evals/questions.yaml")
DEFAULT_REPORT_DIR = Path("evals/reports")


def run_eval(
    questions: Sequence[Question], sut: SystemUnderTest
) -> EvalSummary:
    results: list[QuestionResult] = []
    for question in questions:
        answer = sut.run(question.question)
        results.append(score(question, answer))

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    return EvalSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        results=tuple(results),
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.runner",
        description="Run the LabGraph eval harness against a System Under Test.",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help="Path to the questions YAML file (default: evals/questions.yaml).",
    )
    parser.add_argument(
        "--sut",
        default="null",
        help=(
            "System Under Test: 'null' (dry-run), 'baseline' (legacy retrieval), "
            "or 'graph' (graph-aware retrieval)."
        ),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Write the Markdown report to this path.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write the JSON report to this path.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="Exit with non-zero status if pass rate is below this threshold (0-1).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override the SUT retrieval context limit.",
    )
    return parser.parse_args(argv)


def _print_console_summary(summary: EvalSummary) -> None:
    sys.stdout.write(
        "eval: {passed}/{total} passed ({rate:.0%})\n".format(
            passed=summary.passed,
            total=summary.total,
            rate=summary.pass_rate,
        )
    )
    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        sys.stdout.write(f"  [{status}] {result.question_id}\n")
        if not result.passed:
            for reason in result.reasons:
                sys.stdout.write(f"      - {reason}\n")


def _write_reports(
    summary: EvalSummary,
    questions: Sequence[Question],
    sut_name: str,
    output_md: Path | None,
    output_json: Path | None,
) -> None:
    questions_by_id = {q.id: q for q in questions}
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(
            render_markdown(summary, questions_by_id, sut_name),
            encoding="utf-8",
        )
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            render_json(summary, sut_name),
            encoding="utf-8",
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.top_k is not None and args.top_k < 1:
        raise ValueError("--top-k must be at least 1")
    questions: Tuple[Question, ...] = load_questions(args.questions)
    sut = get_sut(args.sut, top_k=args.top_k)
    summary = run_eval(questions, sut)
    _print_console_summary(summary)
    _write_reports(
        summary,
        questions,
        sut.name,
        args.output_md,
        args.output_json,
    )
    if args.min_pass_rate is not None and summary.pass_rate < args.min_pass_rate:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
