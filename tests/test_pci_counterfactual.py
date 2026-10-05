from datetime import datetime, timedelta, timezone

from seraph.continuity import ContinuityEngine
from seraph.counterfactual import CounterfactualEngine, Intervention
from seraph.core.enums import EntityType, EpistemicStatus, InterventionType, RelationshipType, ShockType
from seraph.core.ids import deterministic_id
from seraph.core.types import EntityRef, Relationship
from seraph.entities.models import Entity
from seraph.graph.store import TemporalGraph
from seraph.shocks import Shock, ShockPropagator


UTC = timezone.utc


def entity(kind: EntityType, name: str) -> Entity:
    return Entity(
        entity_id=deterministic_id("entity", "test", kind.value, name.casefold()),
        entity_type=kind,
        canonical_name=name,
        namespace="test",
        epistemic_status=EpistemicStatus.OBSERVED,
    )


def test_upstream_intervention_changes_downstream_counterfactual() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=24)
    source = entity(EntityType.SATELLITE, "Source")
    middle = entity(EntityType.SERVICE, "Middle")
    target = entity(EntityType.SERVICE, "Target")

    graph = TemporalGraph()
    for item in (source, middle, target):
        graph.add_entity(item)

    def relationship(a: Entity, b: Entity) -> Relationship:
        return Relationship(
            relationship_id=deterministic_id(
                "rel", a.entity_id, b.entity_id, RelationshipType.SUPPORTS.value,
                start.isoformat(), end.isoformat()
            ),
            source=EntityRef(entity_id=a.entity_id),
            target=EntityRef(entity_id=b.entity_id),
            relationship_type=RelationshipType.SUPPORTS,
            valid_from=start,
            valid_to=end,
            confidence=1.0,
            weight=1.0,
        )

    graph.add_relationship(relationship(source, middle))
    graph.add_relationship(relationship(middle, target))

    shock = Shock(
        shock_id=deterministic_id(
            "shock", "test", ShockType.OUTAGE.value, source.entity_id,
            start.isoformat(), end.isoformat(), 0.8
        ),
        name="test",
        shock_type=ShockType.OUTAGE,
        source_entity_id=source.entity_id,
        start=start,
        end=end,
        severity=0.8,
    )

    engine = CounterfactualEngine(ShockPropagator(graph), ContinuityEngine())
    result = engine.compare(
        shock=shock,
        entity_id=target.entity_id,
        intervention=Intervention(
            intervention_id="protect-middle",
            name="Protect middle",
            intervention_type=InterventionType.HARDENING,
            cost_usd=1_000_000.0,
            protected_entities=(middle.entity_id,),
            transmission_reduction=0.75,
        ),
    )

    assert result.counterfactual_minimum_capacity > result.baseline_minimum_capacity
    assert result.continuity_gain > 0.0
