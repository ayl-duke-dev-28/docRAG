from typing import List, Tuple

from .schema import Answer, Question, QuestionResult


def score(question: Question, answer: Answer) -> QuestionResult:
    matched_entities, missing_entities = _partition_entities(
        question.expected_entities, answer.text
    )
    matched_sources, missing_sources = _partition_sources(
        question.expected_sources, answer.sources
    )
    distinct_sources = len({s for s in answer.sources if s})

    reasons: List[str] = []
    if missing_entities:
        reasons.append(
            "missing entities in answer text: " + ", ".join(missing_entities)
        )
    if missing_sources:
        reasons.append(
            "expected sources not retrieved: " + ", ".join(missing_sources)
        )
    if distinct_sources < question.min_distinct_sources:
        reasons.append(
            "multi-hop coverage failed: retrieved {got} distinct source(s), "
            "need >= {want}".format(
                got=distinct_sources, want=question.min_distinct_sources
            )
        )

    passed = not reasons
    return QuestionResult(
        question_id=question.id,
        passed=passed,
        matched_entities=tuple(matched_entities),
        missing_entities=tuple(missing_entities),
        matched_sources=tuple(matched_sources),
        missing_sources=tuple(missing_sources),
        distinct_sources=distinct_sources,
        reasons=tuple(reasons),
    )


def _partition_entities(
    expected: Tuple[str, ...], text: str
) -> Tuple[List[str], List[str]]:
    haystack = text.lower()
    matched: List[str] = []
    missing: List[str] = []
    for entity in expected:
        needle = entity.strip().lower()
        if not needle:
            continue
        if needle in haystack:
            matched.append(entity)
        else:
            missing.append(entity)
    return matched, missing


def _partition_sources(expected, retrieved: Tuple[str, ...]) -> Tuple[List[str], List[str]]:
    retrieved_set = {r for r in retrieved if r}
    matched: List[str] = []
    missing: List[str] = []
    for source in expected:
        if source.filename in retrieved_set:
            matched.append(source.filename)
        else:
            missing.append(source.filename)
    return matched, missing
