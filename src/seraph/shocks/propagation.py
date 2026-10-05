from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from seraph.core.enums import EpistemicStatus
from seraph.core.time import ensure_utc
from seraph.graph.store import TemporalGraph
from seraph.shocks.models import Shock


@dataclass(frozen=True, slots=True)
class PropagationEvent:
    entity_id: str
    severity: float
    depth: int
    path_entity_ids: tuple[str, ...]
    path_relationship_ids: tuple[str, ...]
    status: EpistemicStatus
    effective_at: datetime


class ShockPropagator:
    """Deterministic dependency-cascade propagation with explicit modeled status."""

    def __init__(self, graph: TemporalGraph) -> None:
        self.graph = graph

    def propagate(self, shock: Shock, *, max_hops: int = 32, threshold: float = 0.01) -> tuple[PropagationEvent, ...]:
        if max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        at = ensure_utc(shock.start)
        first = PropagationEvent(
            entity_id=shock.source_entity_id,
            severity=shock.severity,
            depth=0,
            path_entity_ids=(shock.source_entity_id,),
            path_relationship_ids=(),
            status=EpistemicStatus.MODELED,
            effective_at=at,
        )
        frontier: list[PropagationEvent] = [first]
        best: dict[str, float] = {shock.source_entity_id: shock.severity}
        out: list[PropagationEvent] = [first]
        while frontier:
            current = frontier.pop(0)
            if current.depth >= max_hops:
                continue
            for edge in self.graph.edges_from(current.entity_id, at=at):
                propagated = current.severity * min(1.0, edge.confidence) * min(1.0, edge.weight)
                if propagated < threshold:
                    continue
                target = edge.target.entity_id
                if propagated <= best.get(target, -1.0):
                    continue
                best[target] = propagated
                event = PropagationEvent(
                    entity_id=target,
                    severity=min(1.0, propagated),
                    depth=current.depth + 1,
                    path_entity_ids=(*current.path_entity_ids, target),
                    path_relationship_ids=(*current.path_relationship_ids, edge.relationship_id),
                    status=EpistemicStatus.MODELED,
                    effective_at=at,
                )
                out.append(event)
                frontier.append(event)
        return tuple(out)
