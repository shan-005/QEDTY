from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from seraph.core.enums import EpistemicStatus
from seraph.core.time import ensure_utc
from seraph.graph.store import TemporalGraph
from seraph.shocks.models import Shock


@dataclass(frozen=True, slots=True)
class PropagationEvent:
    """One strongest-evidence propagation path to an entity."""

    entity_id: str
    severity: float
    depth: int
    path_entity_ids: tuple[str, ...]
    path_relationship_ids: tuple[str, ...]
    status: EpistemicStatus
    effective_at: datetime


class ShockPropagator:
    """Deterministic strongest-path shock propagation over a temporal graph.

    This is a declared model, not a causal estimator. Edge confidence and
    transmission weight attenuate severity; node-level intervention reductions
    are applied before traversing a protected node's outgoing relationships.
    """

    def __init__(self, graph: TemporalGraph) -> None:
        self.graph = graph

    def propagate(
        self,
        shock: Shock,
        *,
        max_hops: int = 32,
        threshold: float = 0.01,
        node_transmission_reduction: dict[str, float] | None = None,
        node_capacity_gain: dict[str, float] | None = None,
    ) -> tuple[PropagationEvent, ...]:
        if max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        reductions = dict(node_transmission_reduction or {})
        capacity_gains = dict(node_capacity_gain or {})
        for entity_id, value in reductions.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"node transmission reduction out of range: {entity_id}")
        for entity_id, value in capacity_gains.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"node capacity gain out of range: {entity_id}")

        at = ensure_utc(shock.start)
        source_severity = shock.severity * (1.0 - reductions.get(shock.source_entity_id, 0.0))
        source_severity = min(1.0, max(0.0, source_severity))

        first = PropagationEvent(
            entity_id=shock.source_entity_id,
            severity=source_severity,
            depth=0,
            path_entity_ids=(shock.source_entity_id,),
            path_relationship_ids=(),
            status=EpistemicStatus.MODELED,
            effective_at=at,
        )
        frontier: deque[PropagationEvent] = deque([first])
        best: dict[str, float] = {shock.source_entity_id: source_severity}
        out: list[PropagationEvent] = [first]

        while frontier:
            current = frontier.popleft()
            if current.depth >= max_hops or current.severity < threshold:
                continue

            for edge in self.graph.edges_from(current.entity_id, at=at):
                propagated = current.severity * min(1.0, edge.confidence) * min(1.0, edge.weight)
                propagated *= 1.0 - reductions.get(edge.target.entity_id, 0.0)
                propagated = min(1.0, max(0.0, propagated))
                if propagated < threshold:
                    continue

                target = edge.target.entity_id
                if propagated <= best.get(target, -1.0):
                    continue

                # Capacity gain is an intervention-side resilience adjustment.
                # It reduces effective impairment without claiming that the
                # underlying dependency disappeared.
                if target in capacity_gains:
                    propagated *= 1.0 - capacity_gains[target]
                    propagated = min(1.0, max(0.0, propagated))
                    if propagated < threshold:
                        continue

                best[target] = propagated
                event = PropagationEvent(
                    entity_id=target,
                    severity=propagated,
                    depth=current.depth + 1,
                    path_entity_ids=(*current.path_entity_ids, target),
                    path_relationship_ids=(*current.path_relationship_ids, edge.relationship_id),
                    status=EpistemicStatus.COUNTERFACTUAL if reductions or capacity_gains else EpistemicStatus.MODELED,
                    effective_at=at,
                )
                out.append(event)
                frontier.append(event)

        return tuple(out)
