import json
from dataclasses import asdict
from typing import Dict, Tuple

from .schema import EvalSummary, Question, QuestionResult


def render_markdown(
    summary: EvalSummary,
    questions_by_id: Dict[str, Question],
    sut_name: str,
) -> str:
    lines = [
        f"# Eval report — SUT: `{sut_name}`",
        "",
        f"- Total: **{summary.total}**",
        f"- Passed: **{summary.passed}**",
        f"- Failed: **{summary.failed}**",
        f"- Pass rate: **{summary.pass_rate:.0%}**",
        "",
        "## Per-question results",
        "",
        "| ID | Status | Distinct sources | Reasons |",
        "|----|--------|------------------|---------|",
    ]
    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        reasons = "; ".join(result.reasons) if result.reasons else "-"
        lines.append(
            "| {qid} | {status} | {distinct} | {reasons} |".format(
                qid=result.question_id,
                status=status,
                distinct=result.distinct_sources,
                reasons=_escape_pipe(reasons),
            )
        )

    lines.append("")
    lines.append("## Failing questions in detail")
    lines.append("")

    failing = [r for r in summary.results if not r.passed]
    if not failing:
        lines.append("_All questions passed._")
    else:
        for result in failing:
            question = questions_by_id.get(result.question_id)
            question_text = question.question if question else "(unknown)"
            lines.append(f"### {result.question_id}")
            lines.append("")
            lines.append(f"> {question_text}")
            lines.append("")
            if result.missing_entities:
                lines.append(
                    "- Missing entities: " + ", ".join(result.missing_entities)
                )
            if result.missing_sources:
                lines.append(
                    "- Missing sources: " + ", ".join(result.missing_sources)
                )
            if result.matched_sources:
                lines.append(
                    "- Matched sources: " + ", ".join(result.matched_sources)
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(summary: EvalSummary, sut_name: str) -> str:
    payload = {
        "sut": sut_name,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "pass_rate": summary.pass_rate,
        "results": [_result_to_dict(r) for r in summary.results],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _result_to_dict(result: QuestionResult) -> Dict:
    data = asdict(result)
    for key, value in list(data.items()):
        if isinstance(value, tuple):
            data[key] = list(value)
    return data


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")
