"""Builders and deterministic graph composition helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship

from .store import TemporalGraph

if TYPE_CHECKING:
    from collections.abc import Iterable

    from seraph.ontology.world import WorldModel


def from_world(world: WorldModel) -> TemporalGraph:
    """Materialize the graph view represented by the ontology world model."""

    graph = TemporalGraph()
    for entity in sorted(world.entities.values(), key=lambda value: value.entity_id):
        graph.add_entity(entity)
    for relationship in sorted(
        world.relationships.values(), key=lambda value: value.relationship_id
    ):
        graph.add_relationship(relationship)
    return graph


def from_items(items: Iterable[Entity | Relationship]) -> TemporalGraph:
    """Construct a graph from entity/relationship items in dependency-safe order."""

    materialized = tuple(items)
    invalid = [item for item in materialized if not isinstance(item, (Entity, Relationship))]
    if invalid:
        raise TypeError(type(invalid[0]).__name__)
    graph = TemporalGraph()
    for entity in sorted(
        (item for item in materialized if isinstance(item, Entity)),
        key=lambda value: value.entity_id,
    ):
        graph.add_entity(entity)
    for relationship in sorted(
        (item for item in materialized if isinstance(item, Relationship)),
        key=lambda value: value.relationship_id,
    ):
        graph.add_relationship(relationship)
    return graph


def merge(*graphs: TemporalGraph) -> TemporalGraph:
    """Deterministically merge graphs, rejecting semantic ID collisions."""

    merged = TemporalGraph()
    for graph in graphs:
        for entity in graph.entities():
            merged.add_entity(entity)
        for relationship in graph.relationships():
            merged.add_relationship(relationship)
    return merged


def induced_subgraph(graph: TemporalGraph, entity_ids: Iterable[str]) -> TemporalGraph:
    """Build an entity-induced graph containing only selected nodes and edges."""

    selected = set(entity_ids)
    known = {entity.entity_id for entity in graph.entities()}
    missing = sorted(selected - known)
    if missing:
        raise KeyError(f"graph entities missing: {missing}")
    return from_items(
        [
            *[entity for entity in graph.entities() if entity.entity_id in selected],
            *[
                relationship
                for relationship in graph.relationships()
                if relationship.source.entity_id in selected
                and relationship.target.entity_id in selected
            ],
        ]
    )
