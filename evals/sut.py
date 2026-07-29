from pathlib import Path
from typing import Optional, Protocol

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


class LabGraphGraphAwareSUT:
    name = "labgraph-graph-aware"

    def __init__(self, top_k: int = 5, graph_path: Optional[Path] = None) -> None:
        self.top_k = top_k
        self.graph_path = graph_path
        self._graph = None

    def run(self, question: str) -> Answer:
        from docrag.config import LABGRAPH_DB_PATH
        from docrag.retrieval import answer as labgraph_answer
        from labgraph.storage import load_graph

        if self._graph is None:
            self._graph = load_graph(self.graph_path or LABGRAPH_DB_PATH)
        response = labgraph_answer(question, top_k=self.top_k, graph=self._graph)
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
    if normalized in {"graph", "graph-aware", "labgraph-graph-aware"}:
        return LabGraphGraphAwareSUT()
    raise ValueError(
        f"Unknown SUT name: {name!r}. Try 'null', 'baseline', or 'graph'."
    )
