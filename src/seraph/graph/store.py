from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from seraph.core.enums import RelationshipType
from seraph.core.ids import content_digest, deterministic_id
from seraph.core.time import ensure_utc
from seraph.core.types import EntityRef, PathResult, Relationship
from seraph.entities.models import Entity
from seraph.graph.edges import edge_is_valid_at
from seraph.graph.schema import GraphSchemaVersion
from seraph.graph.temporal import relationship_sort_key


class GraphSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: GraphSchemaVersion
    created_at: datetime
    entity_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class TemporalGraph:
    """Deterministic in-memory temporal graph with collision detection and stable queries."""

    def __init__(self, schema: GraphSchemaVersion | None = None) -> None:
        self.schema = schema or GraphSchemaVersion()
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._out: dict[str, set[str]] = defaultdict(set)
        self._in: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def add_entity(self, entity: Entity) -> None:
        with self._lock:
            existing = self._entities.get(entity.entity_id)
            if existing is not None and existing != entity:
                raise ValueError(f"entity collision: {entity.entity_id}")
            self._entities[entity.entity_id] = entity

    def add_relationship(self, relationship: Relationship) -> None:
        with self._lock:
            if relationship.source.entity_id not in self._entities:
                raise KeyError(f"relationship source entity not found: {relationship.source.entity_id}")
            if relationship.target.entity_id not in self._entities:
                raise KeyError(f"relationship target entity not found: {relationship.target.entity_id}")
            existing = self._relationships.get(relationship.relationship_id)
            if existing is not None and existing != relationship:
                raise ValueError(f"relationship collision: {relationship.relationship_id}")
            self._relationships[relationship.relationship_id] = relationship
            self._out[relationship.source.entity_id].add(relationship.relationship_id)
            self._in[relationship.target.entity_id].add(relationship.relationship_id)

    def bulk_add(self, entities: Iterable[Entity], relationships: Iterable[Relationship]) -> None:
        entities_list = list(entities)
        relationships_list = list(relationships)
        with self._lock:
            for entity in entities_list:
                self.add_entity(entity)
            for relationship in relationships_list:
                self.add_relationship(relationship)

    def get_entity(self, entity_id: str) -> Entity:
        return self._entities[entity_id]

    def get_relationship(self, relationship_id: str) -> Relationship:
        return self._relationships[relationship_id]

    def entities(self) -> tuple[Entity, ...]:
        with self._lock:
            return tuple(sorted(self._entities.values(), key=lambda e: e.entity_id))

    def relationships(self) -> tuple[Relationship, ...]:
        with self._lock:
            return tuple(sorted(self._relationships.values(), key=relationship_sort_key))

    def neighbors(
        self,
        entity_id: str,
        *,
        direction: str = "out",
        at: datetime | None = None,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Entity, ...]:
        edge_ids = self._out.get(entity_id, set()) if direction == "out" else self._in.get(entity_id, set()) if direction == "in" else None
        if edge_ids is None:
            raise ValueError("direction must be 'out' or 'in'")
        candidates: list[Entity] = []
        for edge_id in sorted(edge_ids):
            edge = self._relationships[edge_id]
            if not edge_is_valid_at(edge, at):
                continue
            if relationship_types and edge.relationship_type not in relationship_types:
                continue
            other_id = edge.target.entity_id if direction == "out" else edge.source.entity_id
            candidates.append(self._entities[other_id])
        return tuple(sorted({entity.entity_id: entity for entity in candidates}.values(), key=lambda e: e.entity_id))

    def edges_from(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Relationship, ...]:
        edges = []
        for relationship_id in self._out.get(entity_id, set()):
            edge = self._relationships[relationship_id]
            if at is not None and not edge_is_valid_at(edge, at):
                continue
            if relationship_types and edge.relationship_type not in relationship_types:
                continue
            edges.append(edge)
        return tuple(sorted(edges, key=relationship_sort_key))

    def edges_to(
        self,
        entity_id: str,
        *,
        at: datetime | None = None,
        relationship_types: set[RelationshipType] | None = None,
    ) -> tuple[Relationship, ...]:
        edges = []
        for relationship_id in self._in.get(entity_id, set()):
            edge = self._relationships[relationship_id]
            if at is not None and not edge_is_valid_at(edge, at):
                continue
            if relationship_types and edge.relationship_type not in relationship_types:
                continue
            edges.append(edge)
        return tuple(sorted(edges, key=relationship_sort_key))

    def shortest_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        at: datetime | None = None,
        max_hops: int = 32,
        relationship_types: set[RelationshipType] | None = None,
        max_results: int = 10,
    ) -> tuple[PathResult, ...]:
        if source_id not in self._entities or target_id not in self._entities:
            raise KeyError("source_id and target_id must exist in the graph")
        if max_hops < 0 or max_results < 1:
            raise ValueError("max_hops must be >= 0 and max_results must be >= 1")
        if source_id == target_id:
            return (PathResult.from_path([source_id], [], 1.0),)

        queue: deque[tuple[str, list[str], list[str], float]] = deque([(source_id, [source_id], [], 1.0)])
        best_depth: dict[str, int] = {source_id: 0}
        results: list[PathResult] = []
        while queue and len(results) < max_results:
            node, nodes, edges, confidence = queue.popleft()
            if len(edges) >= max_hops:
                continue
            for edge in self.edges_from(node, at=at, relationship_types=relationship_types):
                nxt = edge.target.entity_id
                if nxt in nodes:
                    continue
                new_nodes = [*nodes, nxt]
                new_edges = [*edges, edge.relationship_id]
                new_confidence = confidence * edge.confidence
                if nxt == target_id:
                    results.append(PathResult.from_path(new_nodes, new_edges, new_confidence))
                    if len(results) >= max_results:
                        break
                    continue
                depth = len(new_edges)
                if depth <= best_depth.get(nxt, max_hops + 1):
                    best_depth[nxt] = depth
                    queue.append((nxt, new_nodes, new_edges, new_confidence))
        results.sort(key=lambda p: (p.hops, -p.confidence_product, p.entity_ids))
        return tuple(results[:max_results])

    def snapshot(self, created_at: datetime | None = None) -> GraphSnapshot:
        created = ensure_utc(created_at) if created_at else datetime.now().astimezone()
        payload = {
            "schema": self.schema.model_dump(mode="json"),
            "entities": [entity.model_dump(mode="json") for entity in self.entities()],
            "relationships": [relationship.model_dump(mode="json") for relationship in self.relationships()],
        }
        return GraphSnapshot(
            schema_version=self.schema,
            created_at=created,
            entity_count=len(self._entities),
            relationship_count=len(self._relationships),
            content_sha256=content_digest(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema.model_dump(mode="json"),
            "entities": [entity.model_dump(mode="json") for entity in self.entities()],
            "relationships": [relationship.model_dump(mode="json") for relationship in self.relationships()],
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":") if indent is None else None, indent=indent)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TemporalGraph":
        schema = GraphSchemaVersion.model_validate(payload["schema"], strict=False)
        graph = cls(schema=schema)
        entities = [Entity.model_validate(value, strict=False) for value in payload.get("entities", [])]
        relationships = [Relationship.model_validate(value, strict=False) for value in payload.get("relationships", [])]
        graph.bulk_add(entities, relationships)
        return graph

    @classmethod
    def from_json(cls, payload: str) -> "TemporalGraph":
        return cls.from_dict(json.loads(payload))

    def digest(self) -> str:
        return content_digest(self.to_dict())

    def deterministic_query_id(self, name: str, *parameters: object) -> str:
        return deterministic_id("query", self.digest(), name, parameters)
