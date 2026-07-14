from typing import Protocol

from .schema import Answer


class SystemUnderTest(Protocol):
    name: str

    def run(self, question: str) -> Answer: ...


class NullSUT:
    name = "null"

    def run(self, question: str) -> Answer:
        return Answer(text="", sources=())


class LabGraphBaselineSUT:
    name = "labgraph-baseline"

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def run(self, question: str) -> Answer:
        from docrag.retrieval import answer as labgraph_answer

        response = labgraph_answer(question, top_k=self.top_k)
        sources = tuple(
            source.get("filename", "")
            for source in response.get("sources", [])
            if source.get("filename")
        )
        return Answer(text=response.get("answer", ""), sources=sources)


def get_sut(name: str) -> SystemUnderTest:
    normalized = name.strip().lower()
    if normalized in {"null", "none", "dry-run"}:
        return NullSUT()
    if normalized in {"baseline", "labgraph", "labgraph-baseline", "docrag", "docrag-baseline"}:
        return LabGraphBaselineSUT()
    raise ValueError(f"Unknown SUT name: {name!r}. Try 'null' or 'baseline'.")
