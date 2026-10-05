from __future__ import annotations

from datetime import datetime

from seraph.pci.core.enums import RelationshipType
from seraph.pci.core.types import PathResult
from seraph.pci.entities.models import Entity
from seraph.pci.graph.store import TemporalGraph


class GraphQuery:
    def __init__(self, graph: TemporalGraph) -> None:
        self.graph = graph

    def dependencies(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Entity, ...]:
        return self.graph.neighbors(entity_id, direction="out", at=at, relationship_types=relationship_types)

    def dependents(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Entity, ...]:
        return self.graph.neighbors(entity_id, direction="in", at=at, relationship_types=relationship_types)

    def paths(
        self,
        source_id: str,
        target_id: str,
        *,
        at: datetime | None = None,
        max_hops: int = 32,
        relationship_types: set[RelationshipType] | None = None,
        max_results: int = 10,
    ) -> tuple[PathResult, ...]:
        return self.graph.shortest_paths(
            source_id,
            target_id,
            at=at,
            max_hops=max_hops,
            relationship_types=relationship_types,
            max_results=max_results,
        )

    def reachable(
        self,
        source_id: str,
        *,
        at: datetime | None = None,
        max_hops: int = 16,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Entity, ...]:
        seen = {source_id}
        frontier = [source_id]
        for _ in range(max_hops):
            next_frontier: list[str] = []
            for node in frontier:
                for entity in self.graph.neighbors(node, direction="out", at=at, relationship_types=relationship_types):
                    if entity.entity_id not in seen:
                        seen.add(entity.entity_id)
                        next_frontier.append(entity.entity_id)
            if not next_frontier:
                break
            frontier = sorted(next_frontier)
        return tuple(self.graph.get_entity(entity_id) for entity_id in sorted(seen - {source_id}))
