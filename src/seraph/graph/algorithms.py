from __future__ import annotations

from collections import Counter

from .store import TemporalGraph


def indegree_centrality(graph: TemporalGraph) -> dict[str, float]:
    n = max(1, len(graph.entities()))
    counts = Counter(r.target.entity_id for r in graph.relationships())
    return {e.entity_id: counts[e.entity_id] / max(1, n - 1) for e in graph.entities()}


def outdegree_centrality(graph: TemporalGraph) -> dict[str, float]:
    n = max(1, len(graph.entities()))
    counts = Counter(r.source.entity_id for r in graph.relationships())
    return {e.entity_id: counts[e.entity_id] / max(1, n - 1) for e in graph.entities()}
