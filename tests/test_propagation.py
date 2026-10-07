from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from seraph.core.enums import RelationshipType
from seraph.propagation.engine import PropagationEngine, apply_scenario_propagation
from seraph.propagation.interventions import attenuation_for
from seraph.propagation.models import PropagationAggregation, PropagationEvent, PropagationStatus
from seraph.propagation.path import critical_paths, group_by_entity, strongest, top_k
from seraph.propagation.rules import PropagationRule
from seraph.propagation.schema import KEY, json_schema
from seraph.propagation.state import aggregate_impairments


@dataclass(frozen=True)
class NodeRef:
    entity_id: str


@dataclass(frozen=True)
class Edge:
    relationship_id: str
    source: NodeRef
    target: NodeRef
    relationship_type: RelationshipType = RelationshipType.SUPPORTS
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    strength: float = 1.0
    capacity_fraction: float = 1.0
    attributes: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.attributes is None:
            object.__setattr__(self, "attributes", {})


@dataclass(frozen=True)
class ShockStub:
    shock_id: str
    source_entity_id: str
    severity: float
    starts_at: datetime
    ends_at: datetime


class GraphStub:
    def __init__(self, edges: list[Edge]) -> None:
        self.edges = edges

    def edges_from(self, entity_id: str, at: datetime | None = None) -> tuple[Edge, ...]:
        edges = []
        for edge in self.edges:
            if edge.source.entity_id != entity_id:
                continue
            if at is not None:
                if edge.valid_from is not None and at < edge.valid_from:
                    continue
                if edge.valid_to is not None and at >= edge.valid_to:
                    continue
            edges.append(edge)
        return tuple(sorted(edges, key=lambda x: x.relationship_id))


T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)


def shock(shock_id: str, source: str = "a", severity: float = 0.8) -> ShockStub:
    return ShockStub(shock_id, source, severity, T0, T1)


def edge(
    rid: str,
    source: str,
    target: str,
    strength: float = 1.0,
    delay_seconds: float = 0.0,
    relation_type: RelationshipType = RelationshipType.SUPPORTS,
    valid_to: datetime | None = T1,
) -> Edge:
    return Edge(
        rid,
        NodeRef(source),
        NodeRef(target),
        relation_type,
        T0,
        valid_to,
        strength,
        1.0,
        {"latency_seconds": delay_seconds},
    )


def test_legacy_single_shock_contract_and_path() -> None:
    events = PropagationEngine(
        GraphStub([edge("r1", "a", "b", 0.5), edge("r2", "b", "c", 0.5)])
    ).propagate(shock("s1"))
    assert [item.entity_id for item in events] == ["a", "b", "c"]
    assert events[-1].impairment == pytest.approx(0.2)
    assert events[-1].depth == 2
    assert events[-1].path_relationship_ids == ("r1", "r2")


def test_time_respecting_propagation_uses_delay_and_arrival_validity() -> None:
    graph = GraphStub(
        [
            edge("r1", "a", "b", 1.0, 3600),
            edge("r2", "b", "c", 1.0, 86401),
        ]
    )
    events = PropagationEngine(graph).propagate(shock("s1"))
    assert [item.entity_id for item in events] == ["a", "b"]
    assert events[1].effective_at == datetime(2026, 1, 1, 1, tzinfo=UTC)


def test_max_sum_and_noisy_or_aggregation() -> None:
    graph = GraphStub([edge("r1", "a", "c", 0.5), edge("r2", "b", "c", 0.5)])
    shocks = (shock("s1", "a", 0.8), shock("s2", "b", 0.8))
    max_events = PropagationEngine(graph).propagate_many(shocks)
    sum_events = PropagationEngine(
        graph, PropagationRule(aggregation=PropagationAggregation.SUM_CAP)
    ).propagate_many(shocks)
    noisy_events = PropagationEngine(
        graph, PropagationRule(aggregation=PropagationAggregation.NOISY_OR)
    ).propagate_many(shocks)
    assert next(item for item in max_events if item.entity_id == "c").impairment == pytest.approx(
        0.4
    )
    assert next(item for item in sum_events if item.entity_id == "c").impairment == pytest.approx(
        0.8
    )
    assert next(item for item in noisy_events if item.entity_id == "c").impairment == pytest.approx(
        0.64
    )


def test_intervention_attenuation_is_monotone() -> None:
    baseline = attenuation_for("x", {}, {})
    protected = attenuation_for("x", {"x": 0.5}, {"x": 0.5})
    assert baseline == 1.0
    assert protected == pytest.approx(0.25)
    graph = GraphStub([edge("r1", "a", "b", 0.9)])
    base = PropagationEngine(graph).propagate(shock("s1"))
    counterfactual = PropagationEngine(graph).propagate(
        shock("s1"), transmission_reduction={"b": 0.5}, capacity_gain={"b": 0.2}
    )
    base_b = next(item for item in base if item.entity_id == "b")
    cf_b = next(item for item in counterfactual if item.entity_id == "b")
    assert cf_b.impairment < base_b.impairment
    assert cf_b.status.value == "counterfactual"


def test_cycle_control() -> None:
    graph = GraphStub(
        [edge("r1", "a", "b", 0.9), edge("r2", "b", "a", 0.9), edge("r3", "b", "c", 0.9)]
    )
    no_cycles = PropagationEngine(graph).propagate(shock("s1"))
    with_cycles = PropagationEngine(graph, PropagationRule(allow_cycles=True, max_hops=2)).run(
        shock("s1")
    )
    assert not any(item.entity_id == "a" and item.depth > 0 for item in no_cycles)
    assert with_cycles.summary.generated_signals == 4
    assert with_cycles.summary.max_depth == 2


def test_relationship_filter() -> None:
    graph = GraphStub(
        [
            edge("r1", "a", "b", 0.8, relation_type=RelationshipType.SUPPORTS),
            edge("r2", "a", "c", 0.8, relation_type=RelationshipType.DEPENDS_ON),
        ]
    )
    rule = PropagationRule(allowed_relationship_types=(RelationshipType.DEPENDS_ON,))
    events = PropagationEngine(graph, rule).propagate(shock("s1"))
    assert [item.entity_id for item in events] == ["a", "c"]


def test_edge_transmission_factor_attribute() -> None:
    graph = GraphStub(
        [
            Edge(
                "r1",
                NodeRef("a"),
                NodeRef("b"),
                RelationshipType.SUPPORTS,
                T0,
                T1,
                0.8,
                1.0,
                {"propagation_factor": 0.5},
            )
        ]
    )
    events = PropagationEngine(graph).propagate(shock("s1"))
    assert next(item for item in events if item.entity_id == "b").impairment == pytest.approx(0.32)


def test_bounds_produce_explicit_truncation() -> None:
    graph = GraphStub([edge("r1", "a", "b", 0.9)])
    result = PropagationEngine(graph, PropagationRule(max_signals=1)).run(shock("s1"))
    assert result.summary.truncated is True
    assert result.summary.status is PropagationStatus.TRUNCATED
    assert "max_signals" in result.summary.termination_reason


def test_no_initial_signal_is_explicit() -> None:
    result = PropagationEngine(GraphStub([])).run(shock("s1", severity=0.0))
    assert result.events == ()
    assert result.summary.status is PropagationStatus.NO_INITIAL_SIGNAL


def test_result_is_deterministic_under_shock_order() -> None:
    graph = GraphStub([edge("r1", "a", "c", 0.5), edge("r2", "b", "c", 0.7)])
    engine = PropagationEngine(graph, PropagationRule(aggregation=PropagationAggregation.NOISY_OR))
    left = engine.run((shock("s1", "a"), shock("s2", "b")))
    right = engine.run((shock("s2", "b"), shock("s1", "a")))
    assert left.result_id == right.result_id
    assert left.digest == right.digest


def test_path_utilities() -> None:
    graph = GraphStub([edge("r1", "a", "b", 0.6), edge("r2", "a", "c", 0.4)])
    events = PropagationEngine(graph).propagate(shock("s1"))
    assert strongest(events) == events
    assert len(top_k(events, 2)) == 2
    assert set(group_by_entity(events)) == {"a", "b", "c"}
    assert critical_paths(events, k=1)[0].entity_id == "a"


def test_scenario_adapter() -> None:
    scenario = type("ScenarioStub", (), {"shocks": (shock("s1"),)})()
    result = apply_scenario_propagation(GraphStub([edge("r1", "a", "b", 0.5)]), scenario)
    assert result.summary.event_count == 2


def test_event_validation_and_schema_contract() -> None:
    with pytest.raises(ValueError):
        PropagationEvent(
            entity_id="a",
            impairment=0.5,
            depth=1,
            path_entity_ids=("a",),
            path_relationship_ids=("r1",),
            effective_at=T0,
            status="modeled",
        )
    schema = json_schema()
    assert schema["$id"] == KEY
    assert "propagation_result" in schema["properties"]


def test_aggregation_math() -> None:
    assert aggregate_impairments((0.2, 0.4), PropagationAggregation.MAX) == pytest.approx(0.4)
    assert aggregate_impairments((0.2, 0.4), PropagationAggregation.SUM_CAP) == pytest.approx(0.6)
    assert aggregate_impairments((0.2, 0.4), PropagationAggregation.NOISY_OR) == pytest.approx(0.52)
