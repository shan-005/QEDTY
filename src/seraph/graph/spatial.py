"""Spatially aware graph helpers built on the frozen SERAPH Spatial layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from seraph.spatial.geodesy import distance_m
from seraph.spatial.models import Point

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .store import TemporalGraph


def spatial_distance(a: Point, b: Point) -> float:
    """Return exact ellipsoidal distance in meters using the Spatial contract."""

    return distance_m(a, b)


def entity_point(graph: TemporalGraph, entity_id: str) -> Point:
    """Convert an ontology entity carrying lat/lon into the frozen Point model."""

    entity = graph.get_entity(entity_id)
    if entity.latitude is None or entity.longitude is None:
        raise ValueError(f"entity has no spatial coordinates: {entity_id}")
    return Point(latitude=entity.latitude, longitude=entity.longitude)


def edge_length_m(graph: TemporalGraph, relationship_id: str) -> float:
    """Return geodesic length between the endpoints of a relationship."""

    relationship = graph.get_relationship(relationship_id)
    return spatial_distance(
        entity_point(graph, relationship.source.entity_id),
        entity_point(graph, relationship.target.entity_id),
    )


def entities_within_radius(
    graph: TemporalGraph,
    target: Point,
    radius_m: float,
    *,
    entity_ids: Iterable[str] | None = None,
) -> tuple[tuple[str, float], ...]:
    """Return entities with valid coordinates within an exact geodesic radius."""

    if radius_m < 0:
        raise ValueError("radius_m must be non-negative")
    selected = None if entity_ids is None else set(entity_ids)
    result: list[tuple[str, float]] = []
    for entity in graph.entities():
        if selected is not None and entity.entity_id not in selected:
            continue
        if entity.latitude is None or entity.longitude is None:
            continue
        distance = spatial_distance(
            target, Point(latitude=entity.latitude, longitude=entity.longitude)
        )
        if distance <= radius_m:
            result.append((entity.entity_id, distance))
    result.sort(key=lambda item: (item[1], item[0]))
    return tuple(result)
