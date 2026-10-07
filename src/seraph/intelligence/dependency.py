from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seraph.graph.store import TemporalGraph


@dataclass(frozen=True, slots=True)
class DependencyProfile:
    entity_id: str
    upstream_ids: tuple[str, ...]
    downstream_ids: tuple[str, ...]
    upstream_count: int
    downstream_count: int
    concentration: float
    single_point_of_failure: bool


def critical_upstreams(graph: TemporalGraph, entity_id: str) -> tuple[str, ...]:
    return tuple(sorted(e.entity_id for e in graph.neighbors(entity_id, direction="in")))


def dependency_profile(graph: TemporalGraph, entity_id: str) -> DependencyProfile:
    ups = critical_upstreams(graph, entity_id)
    downs = tuple(sorted(e.entity_id for e in graph.neighbors(entity_id, direction="out")))
    weights = [max(0.0, r.strength * r.capacity_fraction) for r in graph.edges_to(entity_id)]
    total = sum(weights)
    concentration = 0.0 if not weights or total <= 0 else max(weights) / total
    if not isfinite(concentration):
        raise ValueError("non-finite dependency concentration")
    return DependencyProfile(
        entity_id, ups, downs, len(ups), len(downs), concentration, len(ups) == 1
    )
