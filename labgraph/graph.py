from collections import deque
from typing import Dict, Iterator, List, Optional, Tuple

import networkx as nx

from .schema import Entity, EntityKind, Relation, RelationKind


class LabGraph:
    """Small typed knowledge graph for LabGraph.

    Wraps ``networkx.MultiDiGraph`` so multiple relation kinds can exist
    between the same pair of nodes without collisions.
    """

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()

    # ---- mutation ----------------------------------------------------

    def add_entity(self, entity: Entity) -> Entity:
        if entity.id in self._graph:
            merged = self._merge_entity(self._graph.nodes[entity.id]["entity"], entity)
            self._graph.nodes[entity.id]["entity"] = merged
            return merged
        self._graph.add_node(entity.id, entity=entity)
        return entity

    def add_relation(self, relation: Relation) -> Relation:
        if relation.source_id not in self._graph:
            raise KeyError(f"Unknown source entity: {relation.source_id}")
        if relation.target_id not in self._graph:
            raise KeyError(f"Unknown target entity: {relation.target_id}")

        key = (relation.kind.value, tuple(sorted(relation.provenance)))
        self._graph.add_edge(
            relation.source_id,
            relation.target_id,
            key=key,
            relation=relation,
        )
        return relation

    # ---- read --------------------------------------------------------

    @property
    def entity_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def relation_count(self) -> int:
        return self._graph.number_of_edges()

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self._graph

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        if entity_id not in self._graph:
            return None
        return self._graph.nodes[entity_id]["entity"]

    def entities(self, kind: Optional[EntityKind] = None) -> Iterator[Entity]:
        for _, data in self._graph.nodes(data=True):
            entity: Entity = data["entity"]
            if kind is None or entity.kind == kind:
                yield entity

    def relations(
        self, kind: Optional[RelationKind] = None
    ) -> Iterator[Relation]:
        for _, _, data in self._graph.edges(data=True):
            relation: Relation = data["relation"]
            if kind is None or relation.kind == kind:
                yield relation

    def relations_between(
        self,
        source_id: str,
        target_id: str,
        kind: Optional[RelationKind] = None,
    ) -> List[Relation]:
        if source_id not in self._graph or target_id not in self._graph:
            return []
        edge_data = self._graph.get_edge_data(source_id, target_id, default={})
        result: List[Relation] = []
        for data in edge_data.values():
            relation: Relation = data["relation"]
            if kind is None or relation.kind == kind:
                result.append(relation)
        return result

    def neighbors(
        self, entity_id: str, kind: Optional[RelationKind] = None
    ) -> List[Tuple[Relation, Entity]]:
        if entity_id not in self._graph:
            return []
        result: List[Tuple[Relation, Entity]] = []
        for _, target_id, data in self._graph.out_edges(entity_id, data=True):
            relation: Relation = data["relation"]
            if kind is not None and relation.kind != kind:
                continue
            neighbor = self._graph.nodes[target_id]["entity"]
            result.append((relation, neighbor))
        return result

    def shortest_path(
        self, source_id: str, target_id: str, max_depth: int = 3
    ) -> List[str]:
        """Return the node-id path from source to target within max_depth hops.

        Returns an empty list when no path exists within the depth budget.
        Ignores relation kinds; caller can inspect edges after.
        """
        if source_id not in self._graph or target_id not in self._graph:
            return []
        if source_id == target_id:
            return [source_id]

        visited = {source_id}
        parents: Dict[str, str] = {}
        queue: deque = deque([(source_id, 0)])
        found = False
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for _, neighbor, _ in self._graph.out_edges(current, data=True):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                parents[neighbor] = current
                if neighbor == target_id:
                    found = True
                    queue.clear()
                    break
                queue.append((neighbor, depth + 1))

        if not found:
            return []
        path = [target_id]
        while path[-1] != source_id:
            path.append(parents[path[-1]])
        return list(reversed(path))

    def neighborhood(
        self, seed_ids: List[str], max_depth: int = 2
    ) -> List[Entity]:
        """Return the set of entities reachable from any seed within max_depth hops."""
        collected: Dict[str, Entity] = {}
        for seed in seed_ids:
            if seed not in self._graph:
                continue
            for target_id in nx.single_source_shortest_path_length(
                self._graph, seed, cutoff=max_depth
            ):
                if target_id not in collected:
                    collected[target_id] = self._graph.nodes[target_id]["entity"]
        return list(collected.values())

    # ---- internals ---------------------------------------------------

    @staticmethod
    def _merge_entity(existing: Entity, incoming: Entity) -> Entity:
        combined_aliases = list(existing.aliases)
        for alias in incoming.aliases + (incoming.name,):
            if alias and alias != existing.name and alias not in combined_aliases:
                combined_aliases.append(alias)

        merged_attrs: Dict[str, str] = existing.as_attrs_dict()
        for key, value in incoming.attrs:
            merged_attrs.setdefault(key, value)

        return Entity(
            id=existing.id,
            kind=existing.kind,
            name=existing.name,
            aliases=tuple(combined_aliases),
            attrs=tuple(sorted(merged_attrs.items())),
        )
