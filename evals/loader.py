from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from .schema import ExpectedSource, Question


SUPPORTED_VERSION = 1


def load_questions(path: Path) -> Tuple[Question, ...]:
    if not path.exists():
        raise FileNotFoundError(f"Eval file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"Eval file must be a mapping at the top level: {path}")

    version = raw.get("version")
    if version != SUPPORTED_VERSION:
        raise ValueError(
            f"Unsupported eval file version {version!r}; expected {SUPPORTED_VERSION}"
        )

    entries = raw.get("questions")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Eval file must contain a non-empty 'questions' list")

    return tuple(_parse_question(entry, index=i) for i, entry in enumerate(entries))


def _parse_question(entry: Any, index: int) -> Question:
    if not isinstance(entry, dict):
        raise ValueError(f"Question at index {index} must be a mapping, got {type(entry).__name__}")

    question_id = entry.get("id")
    text = entry.get("question")
    if not isinstance(question_id, str) or not question_id.strip():
        raise ValueError(f"Question at index {index} is missing a non-empty 'id'")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Question {question_id!r} is missing a non-empty 'question'")

    expected_entities = _parse_str_list(
        entry.get("expected_entities", []),
        field=f"question {question_id!r} expected_entities",
    )
    expected_sources = tuple(
        _parse_expected_source(src, question_id=question_id, index=i)
        for i, src in enumerate(entry.get("expected_sources", []))
    )
    if not expected_sources:
        raise ValueError(f"Question {question_id!r} must declare at least one expected_source")

    min_distinct_sources = int(entry.get("min_distinct_sources", 2))
    expected_path = _parse_str_list(
        entry.get("expected_path", []),
        field=f"question {question_id!r} expected_path",
    )
    tags = _parse_str_list(entry.get("tags", []), field=f"question {question_id!r} tags")
    notes = str(entry.get("notes", "")).strip()

    return Question(
        id=question_id,
        question=text.strip(),
        expected_entities=expected_entities,
        expected_sources=expected_sources,
        min_distinct_sources=min_distinct_sources,
        expected_path=expected_path,
        tags=tags,
        notes=notes,
    )


def _parse_expected_source(entry: Any, question_id: str, index: int) -> ExpectedSource:
    if isinstance(entry, str):
        return ExpectedSource(filename=entry.strip())
    if isinstance(entry, dict):
        filename = entry.get("filename") or entry.get("paper") or entry.get("meeting_note") or entry.get("doc")
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError(
                f"Question {question_id!r} expected_source[{index}] must have a filename"
            )
        kind = _infer_kind(entry)
        return ExpectedSource(filename=filename.strip(), kind=kind)
    raise ValueError(
        f"Question {question_id!r} expected_source[{index}] must be a string or mapping"
    )


def _infer_kind(entry: Dict[str, Any]) -> str:
    if "kind" in entry:
        return str(entry["kind"]).strip() or "unspecified"
    for key in ("paper", "meeting_note", "doc", "email", "slack"):
        if key in entry:
            return key
    return "unspecified"


def _parse_str_list(value: Any, field: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list, got {type(value).__name__}")
    items: List[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field}[{i}] must be a string, got {type(item).__name__}")
        stripped = item.strip()
        if stripped:
            items.append(stripped)
    return tuple(items)
