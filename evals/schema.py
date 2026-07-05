from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ExpectedSource:
    filename: str
    kind: str = "unspecified"


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected_entities: Tuple[str, ...]
    expected_sources: Tuple[ExpectedSource, ...]
    min_distinct_sources: int = 2
    expected_path: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Question.id must be non-empty")
        if not self.question:
            raise ValueError("Question.question must be non-empty")
        if self.min_distinct_sources < 1:
            raise ValueError("Question.min_distinct_sources must be >= 1")


@dataclass(frozen=True)
class Answer:
    text: str
    sources: Tuple[str, ...]
    traversal_path: Tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    passed: bool
    matched_entities: Tuple[str, ...]
    missing_entities: Tuple[str, ...]
    matched_sources: Tuple[str, ...]
    missing_sources: Tuple[str, ...]
    distinct_sources: int
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalSummary:
    total: int
    passed: int
    failed: int
    results: Tuple[QuestionResult, ...] = field(default_factory=tuple)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total
