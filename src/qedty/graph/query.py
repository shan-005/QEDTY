"""Composable, deterministic graph queries."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from .store import TemporalGraph

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import datetime

    from qedty.core.enums import EntityType, RelationshipType
    from qedty.ontology.entities import Entity
    from qedty.ontology.relations import Relationship

    from .model import GraphPath


def reachable(
    graph: TemporalGraph,
    source: str,
    *,
    at: datetime | None = None,
    max_hops: int = 16,
    relationship_types: set[RelationshipType] | None = None,
) -> tuple[str, ...]:
    """Return directed entities reachable from ``source`` within ``max_hops``."""

    if max_hops < 0:
        raise ValueError("max_hops must be non-negative")
    if not graph.has_entity(source):
        raise KeyError(source)
    seen = {source}
    frontier = [source]
    for _ in range(max_hops):
        nxt: list[str] = []
        for entity_id in frontier:
            for entity in graph.neighbors(
                entity_id, at=at, direction="out", types=relationship_types
            ):
                if entity.entity_id not in seen:
                    seen.add(entity.entity_id)
                    nxt.append(entity.entity_id)
        frontier = sorted(nxt)
        if not frontier:
            break
    return tuple(sorted(seen - {source}))


def neighborhood(
    graph: TemporalGraph,
    source: str,
    *,
    hops: int = 1,
    at: datetime | None = None,
    direction: str = "both",
    relationship_types: set[RelationshipType] | None = None,
) -> tuple[str, ...]:
    """Return the closed k-hop node neighborhood excluding the source."""

    if hops < 0:
        raise ValueError("hops must be non-negative")
    if not graph.has_entity(source):
        raise KeyError(source)
    seen = {source}
    frontier = [source]
    for _ in range(hops):
        next_frontier: list[str] = []
        for node in frontier:
            for entity in graph.neighbors(
                node, at=at, direction=direction, types=relationship_types
            ):
                if entity.entity_id not in seen:
                    seen.add(entity.entity_id)
                    next_frontier.append(entity.entity_id)
        frontier = sorted(next_frontier)
    return tuple(sorted(seen - {source}))


def filter_entities(
    graph: TemporalGraph,
    *,
    entity_ids: Iterable[str] | None = None,
    entity_types: set[EntityType] | None = None,
) -> tuple[Entity, ...]:
    """Filter graph entities by ID and/or ontology type."""

    allowed_ids = None if entity_ids is None else set(entity_ids)
    return tuple(
        entity
        for entity in graph.entities()
        if (allowed_ids is None or entity.entity_id in allowed_ids)
        and (entity_types is None or entity.entity_type in entity_types)
    )


def filter_relationships(
    graph: TemporalGraph,
    *,
    relationship_types: set[RelationshipType] | None = None,
    at: datetime | None = None,
) -> tuple[Relationship, ...]:
    """Filter relationships by type and valid-time instant."""

    relationships = graph.relationships()
    if relationship_types is not None:
        relationships = tuple(r for r in relationships if r.relationship_type in relationship_types)
    if at is not None:
        from .temporal import active_relationships

        relationships = active_relationships(relationships, at)
    return relationships


def induced_subgraph(graph: TemporalGraph, entity_ids: Iterable[str]) -> TemporalGraph:
    """Build the deterministic entity-induced subgraph."""

    selected = set(entity_ids)
    missing = sorted(selected - {entity.entity_id for entity in graph.entities()})
    if missing:
        raise KeyError(f"graph entities missing: {missing}")
    result = TemporalGraph()
    for entity in graph.entities():
        if entity.entity_id in selected:
            result.add_entity(entity)
    for relationship in graph.relationships():
        if relationship.source.entity_id in selected and relationship.target.entity_id in selected:
            result.add_relationship(relationship)
    return result


def shortest_path(
    graph: TemporalGraph,
    source: str,
    target: str,
    *,
    at: datetime | None = None,
    weight: Callable[[Relationship], float] | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> GraphPath | None:
    from .algorithms import shortest_path as dijkstra

    return dijkstra(
        graph,
        source,
        target,
        at=at,
        weight=weight,
        relationship_types=relationship_types,
    )


def entities_on_paths(paths: Iterable[GraphPath]) -> tuple[str, ...]:
    """Return unique entity IDs from one or more paths."""

    ids: set[str] = set()
    for path in paths:
        ids.update(path.entity_ids)
    return tuple(sorted(ids))


def relationship_cut(
    graph: TemporalGraph,
    source: str,
    target: str,
    relationship_ids: Iterable[str],
    *,
    at: datetime | None = None,
) -> bool:
    """Test whether removing the selected relationships disconnects source/target."""

    removed = set(relationship_ids)
    if any(not graph.has_relationship(rid) for rid in removed):
        raise KeyError("relationship missing")
    queue = deque([source])
    seen = {source}
    while queue:
        node = queue.popleft()
        if node == target:
            return False
        for edge in graph.edges_from(node, at=at):
            if edge.relationship_id in removed:
                continue
            nxt = edge.target.entity_id
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return target not in seen
