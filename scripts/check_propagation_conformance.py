from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from seraph.core.enums import RelationshipType
from seraph.propagation.engine import PropagationEngine
from seraph.propagation.models import PropagationAggregation, PropagationStatus
from seraph.propagation.rules import PropagationRule
from seraph.propagation.schema import KEY, json_schema


@dataclass(frozen=True)
class Node:
    entity_id: str


@dataclass(frozen=True)
class Edge:
    relationship_id: str
    source: Node
    target: Node
    relationship_type: RelationshipType = RelationshipType.SUPPORTS
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    strength: float = 1.0
    capacity_fraction: float = 1.0
    attributes: dict[str, object] | None = None


@dataclass(frozen=True)
class Shock:
    shock_id: str
    source_entity_id: str
    severity: float
    starts_at: datetime
    ends_at: datetime


class Graph:
    def __init__(self, edges: tuple[Edge, ...]) -> None:
        self.edges = edges

    def edges_from(self, entity_id: str, at: datetime | None = None) -> tuple[Edge, ...]:
        return tuple(
            edge
            for edge in sorted(self.edges, key=lambda item: item.relationship_id)
            if edge.source.entity_id == entity_id
            and (at is None or edge.valid_from is None or at >= edge.valid_from)
            and (at is None or edge.valid_to is None or at < edge.valid_to)
        )


ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
SHOCK = Shock("s1", "a", 0.8, T0, T1)

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    schema = json_schema()
    require(schema["$id"] == KEY, "schema key mismatch")
    print("Propagation schema: PASS")

    graph = Graph(
        (
            Edge("r1", Node("a"), Node("b"), valid_from=T0, valid_to=T1, strength=0.5),
            Edge("r2", Node("b"), Node("c"), valid_from=T0, valid_to=T1, strength=0.5),
        )
    )
    events = PropagationEngine(graph).propagate(SHOCK)
    require(len(events) == 3 and events[-1].impairment == 0.2, "basic propagation mismatch")
    print("Propagation deterministic cascade: PASS")

    graph_multi = Graph(
        (
            Edge("r1", Node("a"), Node("c"), valid_from=T0, valid_to=T1, strength=0.5),
            Edge("r2", Node("b"), Node("c"), valid_from=T0, valid_to=T1, strength=0.5),
        )
    )
    result = PropagationEngine(
        graph_multi,
        PropagationRule(aggregation=PropagationAggregation.NOISY_OR),
    ).run((SHOCK, Shock("s2", "b", 0.8, T0, T1)))
    c = next(event for event in result.events if event.entity_id == "c")
    require(abs(c.impairment - 0.64) < 1e-12, "aggregation mismatch")
    print("Propagation multi-shock aggregation: PASS")

    delay_graph = Graph(
        (Edge("r1", Node("a"), Node("b"), valid_from=T0, valid_to=T1, strength=1.0, attributes={"latency_seconds": 3600}),)
    )
    delayed = PropagationEngine(delay_graph).propagate(SHOCK)
    require(delayed[1].effective_at.isoformat() == "2026-01-01T01:00:00+00:00", "delay mismatch")
    print("Propagation temporal path: PASS")

    bounded = PropagationEngine(graph, PropagationRule(max_signals=1)).run(SHOCK)
    require(bounded.summary.status is PropagationStatus.TRUNCATED, "bound mismatch")
    print("Propagation bounds: PASS")

    vectors = json.loads((ROOT / "tests" / "propagation_golden_vectors.json").read_text())
    require(vectors["contract"] == KEY, "golden vector contract mismatch")
    require(len(vectors["vectors"]) == 8, "golden vector count mismatch")
    print("Propagation golden vectors: 8/8 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
