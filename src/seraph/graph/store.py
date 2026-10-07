"""Deterministic, temporal, typed in-memory property graph store."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from heapq import heappop, heappush
from threading import RLock
from typing import TYPE_CHECKING

from seraph.core.hash import sha256_hex
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship

from .model import GraphPath, GraphSnapshot, GraphStats
from .temporal import active

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from seraph.core.enums import RelationshipType


class TemporalGraph:
    """Thread-safe directed graph with deterministic adjacency indexes.

    Edges are immutable ontology relationships; updates are modeled as
    collision-safe replacement of the exact deterministic relationship id.
    This keeps graph state reproducible and makes snapshot/query results stable.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._entities: dict[str, Entity] = {}
        self._rels: dict[str, Relationship] = {}
        self._out: defaultdict[str, set[str]] = defaultdict(set)
        self._in: defaultdict[str, set[str]] = defaultdict(set)
        self._out_by_type: defaultdict[tuple[str, RelationshipType], set[str]] = defaultdict(set)
        self._in_by_type: defaultdict[tuple[str, RelationshipType], set[str]] = defaultdict(set)
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def __len__(self) -> int:
        return len(self._entities)

    def add_entity(self, entity: Entity) -> None:
        with self._lock:
            previous = self._entities.get(entity.entity_id)
            if previous is not None and previous != entity:
                raise ValueError(f"entity collision: {entity.entity_id}")
            if previous is None:
                self._entities[entity.entity_id] = entity
                self._revision += 1

    def add_relationship(self, relationship: Relationship) -> None:
        with self._lock:
            if (
                relationship.source.entity_id not in self._entities
                or relationship.target.entity_id not in self._entities
            ):
                raise KeyError("relationship endpoint missing")
            previous = self._rels.get(relationship.relationship_id)
            if previous is not None and previous != relationship:
                raise ValueError(f"relationship collision: {relationship.relationship_id}")
            if previous is None:
                self._rels[relationship.relationship_id] = relationship
                self._index_relationship(relationship)
                self._revision += 1

    def add_many(self, items: Iterable[Entity | Relationship]) -> None:
        """Insert a deterministic batch, with entities resolved before edges."""

        materialized = tuple(items)
        invalid = [item for item in materialized if not isinstance(item, (Entity, Relationship))]
        if invalid:
            raise TypeError(type(invalid[0]).__name__)
        entities = [item for item in materialized if isinstance(item, Entity)]
        relationships = [item for item in materialized if isinstance(item, Relationship)]
        for entity in sorted(entities, key=lambda value: value.entity_id):
            self.add_entity(entity)
        for relationship in sorted(relationships, key=lambda value: value.relationship_id):
            self.add_relationship(relationship)

    def remove_relationship(self, relationship_id: str) -> Relationship | None:
        with self._lock:
            relationship = self._rels.pop(relationship_id, None)
            if relationship is None:
                return None
            self._deindex_relationship(relationship)
            self._revision += 1
            return relationship

    def remove_entity(self, entity_id: str, *, cascade: bool = False) -> Entity | None:
        with self._lock:
            entity = self._entities.get(entity_id)
            if entity is None:
                return None
            incident = sorted(set(self._out.get(entity_id, ())) | set(self._in.get(entity_id, ())))
            if incident and not cascade:
                raise ValueError("cannot remove entity with incident relationships")
            for relationship_id in incident:
                self.remove_relationship(relationship_id)
            self._entities.pop(entity_id)
            self._out.pop(entity_id, None)
            self._in.pop(entity_id, None)
            self._revision += 1
            return entity

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def has_relationship(self, relationship_id: str) -> bool:
        return relationship_id in self._rels

    def get_entity(self, entity_id: str) -> Entity:
        try:
            return self._entities[entity_id]
        except KeyError as exc:
            raise KeyError(f"graph entity missing: {entity_id}") from exc

    def get_relationship(self, relationship_id: str) -> Relationship:
        try:
            return self._rels[relationship_id]
        except KeyError as exc:
            raise KeyError(f"graph relationship missing: {relationship_id}") from exc

    def entities(self) -> tuple[Entity, ...]:
        with self._lock:
            return tuple(sorted(self._entities.values(), key=lambda item: item.entity_id))

    def relationships(self) -> tuple[Relationship, ...]:
        with self._lock:
            return tuple(sorted(self._rels.values(), key=lambda item: item.relationship_id))

    def edges_from(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        types: set[RelationshipType] | frozenset[RelationshipType] | None = None,
    ) -> tuple[Relationship, ...]:
        ids = self._relationship_ids(entity_id, direction="out", types=types)
        return tuple(
            relationship
            for relationship in (self._rels[rid] for rid in ids)
            if at is None or active(relationship, at)
        )

    def edges_to(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        types: set[RelationshipType] | frozenset[RelationshipType] | None = None,
    ) -> tuple[Relationship, ...]:
        ids = self._relationship_ids(entity_id, direction="in", types=types)
        return tuple(
            relationship
            for relationship in (self._rels[rid] for rid in ids)
            if at is None or active(relationship, at)
        )

    def neighbors(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        direction: str = "out",
        types: set[RelationshipType] | frozenset[RelationshipType] | None = None,
    ) -> tuple[Entity, ...]:
        if direction not in {"out", "in", "both"}:
            raise ValueError("direction must be 'out', 'in', or 'both'")
        relationships: list[Relationship] = []
        if direction in {"out", "both"}:
            relationships.extend(self.edges_from(entity_id, at=at, types=types))
        if direction in {"in", "both"}:
            relationships.extend(self.edges_to(entity_id, at=at, types=types))
        neighbor_ids: set[str] = set()
        for relationship in relationships:
            if relationship.source.entity_id == entity_id:
                neighbor_ids.add(relationship.target.entity_id)
            if relationship.target.entity_id == entity_id:
                neighbor_ids.add(relationship.source.entity_id)
        return tuple(self._entities[eid] for eid in sorted(neighbor_ids))

    def snapshot(self, at: datetime) -> GraphSnapshot:
        """Return the deterministic entity/edge membership at ``at``."""

        relationships = tuple(
            relationship for relationship in self.relationships() if active(relationship, at)
        )
        return GraphSnapshot(
            at=at,
            entity_ids=tuple(entity.entity_id for entity in self.entities()),
            relationship_ids=tuple(r.relationship_id for r in relationships),
        )

    def stats(self, *, at: datetime | None = None) -> GraphStats:
        entities = self.entities()
        relationships = tuple(
            relationship
            for relationship in self.relationships()
            if at is None or active(relationship, at)
        )
        indegree = {entity.entity_id: 0 for entity in entities}
        outdegree = {entity.entity_id: 0 for entity in entities}
        self_loops = 0
        for relationship in relationships:
            outdegree[relationship.source.entity_id] += 1
            indegree[relationship.target.entity_id] += 1
            if relationship.source.entity_id == relationship.target.entity_id:
                self_loops += 1
        n = len(entities)
        possible = n * max(n - 1, 0)
        return GraphStats(
            entities=n,
            relationships=len(relationships),
            density=(len(relationships) / possible) if possible else 0.0,
            self_loops=self_loops,
            isolated_entities=sum(
                1
                for entity in entities
                if indegree[entity.entity_id] + outdegree[entity.entity_id] == 0
            ),
            average_in_degree=(len(relationships) / n) if n else 0.0,
            average_out_degree=(len(relationships) / n) if n else 0.0,
            max_in_degree=max(indegree.values(), default=0),
            max_out_degree=max(outdegree.values(), default=0),
        )

    def shortest_paths(
        self,
        source: str,
        target: str,
        *,
        at: datetime | None = None,
        max_hops: int = 16,
        max_results: int = 10,
        max_expansions: int = 100_000,
    ) -> tuple[GraphPath, ...]:
        """Return highest-reliability simple paths in deterministic order."""

        if source not in self._entities or target not in self._entities:
            raise KeyError("graph endpoint missing")
        if max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        if max_expansions <= 0:
            raise ValueError("max_expansions must be positive")
        if source == target:
            return (GraphPath((source,), (), 1.0, 0.0),)

        queue: list[tuple[float, int, tuple[str, ...], tuple[str, ...], str]] = []
        heappush(queue, (-1.0, 0, (source,), (), source))
        results: list[GraphPath] = []
        expansions = 0
        while queue and len(results) < max_results and expansions < max_expansions:
            neg_score, hops, nodes, relationship_ids, node = heappop(queue)
            score = -neg_score
            if node == target:
                results.append(GraphPath(nodes, relationship_ids, score))
                continue
            if hops >= max_hops:
                continue
            expansions += 1
            for relationship in self.edges_from(node, at=at):
                next_node = relationship.target.entity_id
                if next_node in nodes:
                    continue
                edge_score = relationship.strength * relationship.capacity_fraction
                next_score = score * edge_score
                next_nodes = (*nodes, next_node)
                next_relationship_ids = (*relationship_ids, relationship.relationship_id)
                heappush(
                    queue,
                    (-next_score, hops + 1, next_nodes, next_relationship_ids, next_node),
                )
        results.sort(
            key=lambda path: (-path.score, path.hops, path.entity_ids, path.relationship_ids)
        )
        return tuple(results)

    def digest(self) -> str:
        """Return a stable SHA-256 of the semantic graph contents."""

        return sha256_hex(
            {
                "entities": [entity.model_dump(mode="json") for entity in self.entities()],
                "relationships": [
                    relationship.model_dump(mode="json") for relationship in self.relationships()
                ],
            }
        )

    def _index_relationship(self, relationship: Relationship) -> None:
        source = relationship.source.entity_id
        target = relationship.target.entity_id
        relation_type = relationship.relationship_type
        self._out[source].add(relationship.relationship_id)
        self._in[target].add(relationship.relationship_id)
        self._out_by_type[(source, relation_type)].add(relationship.relationship_id)
        self._in_by_type[(target, relation_type)].add(relationship.relationship_id)

    def _deindex_relationship(self, relationship: Relationship) -> None:
        source = relationship.source.entity_id
        target = relationship.target.entity_id
        relation_type = relationship.relationship_type
        self._out[source].discard(relationship.relationship_id)
        self._in[target].discard(relationship.relationship_id)
        self._out_by_type[(source, relation_type)].discard(relationship.relationship_id)
        self._in_by_type[(target, relation_type)].discard(relationship.relationship_id)
        if not self._out.get(source):
            self._out.pop(source, None)
        if not self._in.get(target):
            self._in.pop(target, None)
        if not self._out_by_type.get((source, relation_type)):
            self._out_by_type.pop((source, relation_type), None)
        if not self._in_by_type.get((target, relation_type)):
            self._in_by_type.pop((target, relation_type), None)

    def _relationship_ids(
        self,
        entity_id: str,
        *,
        direction: str,
        types: set[RelationshipType] | frozenset[RelationshipType] | None,
    ) -> tuple[str, ...]:
        if entity_id not in self._entities:
            raise KeyError(f"graph entity missing: {entity_id}")
        if direction not in {"out", "in"}:
            raise ValueError("direction must be 'out' or 'in'")
        if not types:
            ids = (
                self._out.get(entity_id, ()) if direction == "out" else self._in.get(entity_id, ())
            )
            return tuple(sorted(ids))
        selected: set[str] = set()
        index = self._out_by_type if direction == "out" else self._in_by_type
        for relation_type in sorted(types, key=lambda value: value.value):
            selected.update(index.get((entity_id, relation_type), ()))
        return tuple(sorted(selected))
