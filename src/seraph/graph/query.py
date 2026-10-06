from datetime import datetime

from seraph.core.enums import RelationshipType

from .store import TemporalGraph


def reachable(
    graph: TemporalGraph,
    source: str,
    *,
    at: datetime | None = None,
    max_hops: int = 16,
    relationship_types: set[RelationshipType] | None = None,
) -> tuple[str, ...]:
    seen = {source}
    frontier = [source]
    for _ in range(max_hops):
        nxt = []
        for eid in frontier:
            for e in graph.neighbors(eid, at=at, direction="out", types=relationship_types):
                if e.entity_id not in seen:
                    seen.add(e.entity_id)
                    nxt.append(e.entity_id)
        frontier = sorted(nxt)
        if not frontier:
            break
    return tuple(sorted(seen - {source}))
