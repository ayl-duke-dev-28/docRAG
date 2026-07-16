from typing import Tuple

from .graph import LabGraph
from .schema import Entity, normalize


def _bounded(slug: str) -> str:
    """Wrap a slug in separators so matching respects token boundaries.

    ``normalize`` joins tokens with "-", so surrounding both the needle and the
    haystack with "-" makes a substring test equivalent to a whole-token test:
    "lora" then matches "-use-lora-here-" but not "-floral-".
    """
    return f"-{slug}-"


def resolve_mentions(graph: LabGraph, question: str) -> Tuple[Entity, ...]:
    """Return the graph entities named in ``question``, ordered by entity id.

    Matches an entity's canonical name or any of its declared aliases. The
    ordering is deterministic so downstream path selection is reproducible.
    """
    haystack = _bounded(normalize(question))
    if haystack == "--":
        return ()

    matched = [
        entity
        for entity in graph.entities()
        if _names_entity(haystack, entity)
    ]
    return tuple(sorted(matched, key=lambda entity: entity.id))


def _names_entity(haystack: str, entity: Entity) -> bool:
    for surface in (entity.name,) + entity.aliases:
        slug = normalize(surface)
        if slug and _bounded(slug) in haystack:
            return True
    return False
