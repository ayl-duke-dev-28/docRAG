from dataclasses import dataclass
from enum import Enum
from itertools import permutations
from typing import List, Optional, Sequence, Tuple

from .graph import LabGraph
from .resolve import resolve_mentions
from .schema import Entity, Relation

DEFAULT_MAX_DEPTH = 4
NEIGHBORHOOD_DEPTH = 1
MAX_NEIGHBORHOOD_ENTITIES = 8


class TraceStatus(str, Enum):
    """Why the trace looks the way it does.

    Every status except FOUND is a designed, user-facing state. A trace is
    never rendered unless it was derived from the question that produced the
    answer beside it.
    """

    FOUND = "found"
    NO_GRAPH = "no_graph"
    NO_ENTITIES = "no_entities"
    PARTIAL = "partial"
    NO_PATH = "no_path"
    ERROR = "error"


@dataclass(frozen=True)
class QuestionTrace:
    status: TraceStatus
    max_depth: int = DEFAULT_MAX_DEPTH
    matched: Tuple[Entity, ...] = ()
    path: Tuple[Entity, ...] = ()
    relations: Tuple[Relation, ...] = ()
    neighborhood: Tuple[Entity, ...] = ()


def trace_for_question(
    graph: LabGraph, question: str, max_depth: int = DEFAULT_MAX_DEPTH
) -> QuestionTrace:
    """Build the graph trace that explains an answer to ``question``.

    Resolves the entities the question names, then walks between them. Returns
    a non-FOUND status rather than an unrelated path when it cannot connect
    them: an honest empty state beats a plausible-looking wrong one.
    """
    if graph.entity_count == 0:
        return QuestionTrace(status=TraceStatus.NO_GRAPH, max_depth=max_depth)

    matched = resolve_mentions(graph, question)
    if not matched:
        return QuestionTrace(status=TraceStatus.NO_ENTITIES, max_depth=max_depth)

    if len(matched) == 1:
        return QuestionTrace(
            status=TraceStatus.PARTIAL,
            max_depth=max_depth,
            matched=matched,
            neighborhood=_neighborhood_of(graph, matched[0]),
        )

    path = _select_path(graph, matched, max_depth)
    if not path:
        return QuestionTrace(
            status=TraceStatus.NO_PATH, max_depth=max_depth, matched=matched
        )

    return _found_trace(graph, matched, path, max_depth)


def trace_between(
    graph: LabGraph,
    source_id: str,
    target_id: str,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> QuestionTrace:
    """Build a trace between two explicitly chosen entities.

    The direct primitive behind ``trace_for_question``, exposed for callers
    that already know both endpoints.
    """
    if graph.entity_count == 0:
        return QuestionTrace(status=TraceStatus.NO_GRAPH, max_depth=max_depth)

    endpoints = _entities_for(graph, (source_id, target_id))
    if len(endpoints) < 2:
        return QuestionTrace(
            status=TraceStatus.NO_ENTITIES, max_depth=max_depth, matched=endpoints
        )

    path = graph.shortest_path(source_id, target_id, max_depth=max_depth)
    if not path:
        return QuestionTrace(
            status=TraceStatus.NO_PATH, max_depth=max_depth, matched=endpoints
        )
    return _found_trace(graph, endpoints, path, max_depth)


def _found_trace(
    graph: LabGraph, matched: Sequence[Entity], path: Sequence[str], max_depth: int
) -> QuestionTrace:
    return QuestionTrace(
        status=TraceStatus.FOUND,
        max_depth=max_depth,
        matched=tuple(matched),
        path=_entities_for(graph, path),
        relations=relations_along_path(graph, path),
    )


def relations_along_path(graph: LabGraph, path: Sequence[str]) -> Tuple[Relation, ...]:
    """Return one relation for each consecutive pair of nodes on ``path``."""
    relations: List[Relation] = []
    for source_id, target_id in zip(path, path[1:]):
        between = graph.relations_between(source_id, target_id)
        if between:
            relations.append(between[0])
    return tuple(relations)


def _select_path(
    graph: LabGraph, matched: Sequence[Entity], max_depth: int
) -> List[str]:
    """Pick the path that best explains the question.

    Tries every ordered pair of named entities, because the graph is directed
    and mention order in the question says nothing about edge direction.
    Prefers the path touching the most named entities, then the shorter one.
    """
    matched_ids = {entity.id for entity in matched}
    best: List[str] = []
    best_score: Optional[Tuple[int, int]] = None

    for source, target in permutations(matched, 2):
        path = graph.shortest_path(source.id, target.id, max_depth=max_depth)
        if not path:
            continue
        score = (len(matched_ids.intersection(path)), -len(path))
        if best_score is None or score > best_score:
            best_score, best = score, path

    return best


def _entities_for(graph: LabGraph, path: Sequence[str]) -> Tuple[Entity, ...]:
    found = (graph.get_entity(entity_id) for entity_id in path)
    return tuple(entity for entity in found if entity is not None)


def _neighborhood_of(graph: LabGraph, entity: Entity) -> Tuple[Entity, ...]:
    # Undirected: a Decision has no outbound edges, but the methods decided in
    # it are exactly the context worth showing.
    nearby = graph.neighborhood(
        [entity.id], max_depth=NEIGHBORHOOD_DEPTH, directed=False
    )
    return tuple(
        node for node in nearby[:MAX_NEIGHBORHOOD_ENTITIES] if node.id != entity.id
    )
