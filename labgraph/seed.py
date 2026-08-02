from typing import Iterable, List, Set, Tuple

from .graph import LabGraph
from .schema import Entity


def seed_entities_from_chunks(
    graph: LabGraph, chunk_ids: Iterable[object]
) -> Tuple[Entity, ...]:
    """Return unique relation endpoints supported by ranked chunk IDs."""
    relations = tuple(graph.relations())
    seeds: List[Entity] = []
    seen: Set[str] = set()

    for raw_chunk_id in chunk_ids:
        chunk_id = str(raw_chunk_id)
        for relation in relations:
            if chunk_id not in relation.provenance:
                continue
            for entity_id in (relation.source_id, relation.target_id):
                if entity_id in seen:
                    continue
                entity = graph.get_entity(entity_id)
                if entity is not None:
                    seeds.append(entity)
                    seen.add(entity_id)

    return tuple(seeds)
