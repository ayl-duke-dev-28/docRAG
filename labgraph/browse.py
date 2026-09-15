"""Search and ranking for the corpus-panel entity browser.

The browser answers "what does LabGraph actually know?" without making the
user ask a question first, so it ranks by connectivity: the entities with the
most typed relations are the ones worth inspecting.
"""

from typing import Dict, List, Optional

from .graph import LabGraph
from .schema import Entity, EntityKind

DEFAULT_ENTITY_LIMIT = 200
MAX_ENTITY_LIMIT = 500


def entity_payload(entity: Entity) -> Dict:
    """Serialize an entity for the API. The canonical entity JSON shape."""
    return {
        "id": entity.id,
        "kind": entity.kind.value,
        "name": entity.name,
        "aliases": list(entity.aliases),
        "attrs": entity.as_attrs_dict(),
    }


def _matches(entity: Entity, query: str) -> bool:
    if not query:
        return True
    return any(
        query in candidate.casefold()
        for candidate in (entity.name, *entity.aliases)
    )


def _browsed_entity(graph: LabGraph, entity: Entity) -> Dict:
    incident = graph.incident_relations(entity.id)
    return {
        **entity_payload(entity),
        "relation_count": len(incident),
        "relations": [
            {
                "kind": relation.kind.value,
                "direction": direction,
                "entity_id": other.id,
                "entity_name": other.name,
            }
            for relation, other, direction in incident
        ],
    }


def browse_entities(
    graph: LabGraph,
    kind: Optional[EntityKind] = None,
    query: str = "",
    limit: int = DEFAULT_ENTITY_LIMIT,
) -> Dict:
    """Return ranked, filtered entities plus the unclamped match total.

    ``total`` counts every match so the UI can say "showing 200 of 412";
    ``returned`` is what survived the limit.
    """
    normalized = (query or "").strip().casefold()
    matches: List[Entity] = [
        entity for entity in graph.entities(kind=kind) if _matches(entity, normalized)
    ]
    ranked = sorted(
        matches,
        key=lambda entity: (
            -len(graph.incident_relations(entity.id)),
            entity.name.casefold(),
        ),
    )
    capped = max(1, min(limit, MAX_ENTITY_LIMIT))
    selected = ranked[:capped]
    return {
        "total": len(matches),
        "returned": len(selected),
        "entities": [_browsed_entity(graph, entity) for entity in selected],
    }
