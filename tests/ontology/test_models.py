from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from seraph.core.enums import EntityType, EpistemicStatus, EventType, RelationshipType
from seraph.core.geometry import GeodeticPoint
from seraph.core.hash import deterministic_id
from seraph.core.types import EntityRef, ExternalIdentifier, SourceRef, TimeWindow
from seraph.core.units import Quantity
from seraph.ontology import (
    Assertion,
    AssertionKind,
    Capability,
    CapabilityKind,
    Entity,
    EntityLifecycle,
    EntityResolution,
    EventPhase,
    Flow,
    FlowKind,
    Relationship,
    ResolutionDecision,
    ResolutionMethod,
    Service,
    WorldEvent,
    WorldModel,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
END = NOW + timedelta(hours=1)
WINDOW = TimeWindow(start=NOW, end=END)


def entity(name: str, kind: EntityType = EntityType.FACILITY) -> Entity:
    normalized_name = " ".join(name.split())
    return Entity(
        entity_id=deterministic_id("entity", "seraph", kind.value, normalized_name.casefold()),
        entity_type=kind,
        canonical_name=name,
        namespace="seraph",
        lifecycle=EntityLifecycle.ACTIVE,
        valid_time=WINDOW,
        observed_at=NOW,
        location=GeodeticPoint(latitude=17.3850, longitude=78.4867),
        external_identifiers=(ExternalIdentifier(namespace="demo", value=name.casefold()),),
    )


def test_entity_identity_and_normalization() -> None:
    item = entity("  Hyderabad   Facility ")
    assert item.canonical_name == "Hyderabad Facility"
    assert item.entity_id == deterministic_id(
        "entity", "seraph", EntityType.FACILITY.value, "hyderabad facility"
    )
    assert item.ref().entity_id == item.entity_id
    assert item.valid_from == NOW
    assert item.valid_to == END


def test_entity_resolution_is_deterministic() -> None:
    item = entity("Satellite A", EntityType.SATELLITE)
    resolution_id = deterministic_id(
        "entity-resolution", item.entity_id, "norad", "12345", "exact_external_id", "accepted"
    )
    resolution = EntityResolution(
        resolution_id=resolution_id,
        entity_id=item.entity_id,
        external_identifier=ExternalIdentifier(namespace="norad", value="12345"),
        method=ResolutionMethod.EXACT_EXTERNAL_ID,
        decision=ResolutionDecision.ACCEPTED,
        score=1.0,
        resolver="test",
        resolved_at=NOW,
    )
    assert resolution.resolution_id == resolution_id


def test_relationship_latency_dimension() -> None:
    a = entity("A")
    b = entity("B")
    rid = deterministic_id("rel", a.entity_id, b.entity_id, "supports", None, None)
    relation = Relationship(
        relationship_id=rid,
        source=a.ref(),
        target=b.ref(),
        relationship_type=RelationshipType.SUPPORTS,
        latency=Quantity(value=Decimal(10), unit="ms"),
    )
    assert relation.effective_strength() == 1.0


def test_event_temporal_identity() -> None:
    item = entity("Event Source")
    event_id = deterministic_id(
        "event", "Outage", EventType.OUTAGE.value, NOW.isoformat(), END.isoformat(), 0.8
    )
    event = WorldEvent(
        event_id=event_id,
        event_type=EventType.OUTAGE,
        name="Outage",
        time=WINDOW,
        severity=0.8,
        impact_fraction=0.4,
        source_entity_ids=(item.entity_id,),
        phase=EventPhase.ACTIVE,
    )
    assert event.starts_at == NOW
    assert event.ends_at == END
    assert event.affects("missing") is False


def test_capacity_uses_core_quantity() -> None:
    owner = entity("Plant", EntityType.POWER_PLANT)
    cid = deterministic_id("capability", owner.entity_id, CapabilityKind.POWER.value, "generation")
    capability = Capability(
        capability_id=cid,
        name="Generation",
        kind=CapabilityKind.POWER,
        nominal_capacity=Quantity(value=Decimal(100), unit="MW"),
        owner=owner.ref(),
        availability_fraction=0.75,
    )
    assert capability.effective_capacity().unit == "MW"
    assert capability.effective_capacity().value == Decimal("75.00")


def test_service_requires_provider_or_capability() -> None:
    sid = deterministic_id("service", "seraph", "positioning")
    with pytest.raises(ValueError):
        Service(service_id=sid, name="Positioning")


def test_flow_requires_distinct_endpoints() -> None:
    a = entity("A")
    fid = deterministic_id(
        "flow",
        FlowKind.ENERGY.value,
        a.entity_id,
        a.entity_id,
        "1",
        "MW",
        NOW.isoformat(),
        END.isoformat(),
    )
    with pytest.raises(ValueError):
        Flow(
            flow_id=fid,
            flow_type=FlowKind.ENERGY,
            source=a.ref(),
            target=a.ref(),
            quantity=Quantity(value=Decimal(1), unit="MW"),
            valid_time=WINDOW,
        )


def test_assertion_supports_relation_and_literal_forms() -> None:
    a = entity("A")
    b = entity("B")
    relation_id = deterministic_id(
        "assertion",
        a.entity_id,
        "seraph:supports",
        b.entity_id,
        None,
        AssertionKind.RELATIONSHIP.value,
        None,
        None,
    )
    relation = Assertion(
        assertion_id=relation_id,
        subject=a.ref(),
        predicate="seraph:supports",
        object_entity=b.ref(),
        kind=AssertionKind.RELATIONSHIP,
        asserted_at=NOW,
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    assert relation.object_id == b.entity_id

    attribute_id = deterministic_id(
        "assertion",
        a.entity_id,
        "seraph:criticality",
        None,
        '{"score":0.8}',
        AssertionKind.ATTRIBUTE.value,
        None,
        None,
    )
    attribute = Assertion(
        assertion_id=attribute_id,
        subject=a.ref(),
        predicate="seraph:criticality",
        value={"score": 0.8},
        kind=AssertionKind.ATTRIBUTE,
        asserted_at=NOW,
        epistemic_status=EpistemicStatus.DERIVED,
        confidence=0.9,
        source=SourceRef(source_id="source:demo"),
    )
    assert attribute.subject_id == a.entity_id


def test_world_model_enforces_referential_integrity_and_transactions() -> None:
    a = entity("A")
    b = entity("B")
    model = WorldModel()
    model.add_many([a, b])
    assert model.summary()["entities"] == 2

    rid = deterministic_id("rel", a.entity_id, b.entity_id, "supports", None, None)
    relation = Relationship(
        relationship_id=rid,
        source=a.ref(),
        target=b.ref(),
        relationship_type=RelationshipType.SUPPORTS,
    )
    model.add(relation)
    assert len(model.relationships_for(a.entity_id)) == 1

    resolution_id = deterministic_id(
        "entity-resolution", a.entity_id, "demo", "a", "exact_external_id", "accepted"
    )
    model.add_resolution(
        EntityResolution(
            resolution_id=resolution_id,
            entity_id=a.entity_id,
            external_identifier=ExternalIdentifier(namespace="demo", value="a"),
            method=ResolutionMethod.EXACT_EXTERNAL_ID,
            decision=ResolutionDecision.ACCEPTED,
            score=1.0,
            resolver="test",
            resolved_at=NOW,
        )
    )
    assert model.find_entity_by_external_identifier("demo", "a") == (a.entity_id,)

    with pytest.raises(KeyError), model.transaction():
        model.add(
            Relationship(
                relationship_id=deterministic_id(
                    "rel", a.entity_id, "missing", "supports", None, None
                ),
                source=a.ref(),
                target=EntityRef(entity_id="missing"),
                relationship_type=RelationshipType.SUPPORTS,
            )
        )
    assert len(model.relationships) == 1
    assert model.snapshot().fingerprint


def test_entity_observation_time_is_independent_from_valid_time() -> None:
    future_window = TimeWindow(start=NOW + timedelta(days=1), end=END + timedelta(days=1))
    item = Entity(
        entity_id=deterministic_id(
            "entity", "seraph", EntityType.FACILITY.value, "planned facility"
        ),
        entity_type=EntityType.FACILITY,
        canonical_name="Planned Facility",
        valid_time=future_window,
        observed_at=NOW,
        lifecycle=EntityLifecycle.PLANNED,
    )
    assert item.observed_at == NOW
    assert item.valid_from == future_window.start


def test_resolution_index_maps_unlisted_external_identifier() -> None:
    item = entity("Resolver Target")
    resolution_id = deterministic_id(
        "entity-resolution",
        item.entity_id,
        "icao",
        "ABCD",
        "exact_external_id",
        "accepted",
    )
    resolution = EntityResolution(
        resolution_id=resolution_id,
        entity_id=item.entity_id,
        external_identifier=ExternalIdentifier(namespace="icao", value="ABCD"),
        method=ResolutionMethod.EXACT_EXTERNAL_ID,
        decision=ResolutionDecision.ACCEPTED,
        score=1.0,
        resolver="test",
        resolved_at=NOW,
    )
    model = WorldModel()
    model.add_many([item, resolution])
    assert model.find_entity_by_external_identifier("icao", "ABCD") == (item.entity_id,)


def test_resolution_index_rejects_conflicting_accepted_mapping() -> None:
    first = entity("First")
    second = entity("Second")
    external = ExternalIdentifier(namespace="demo", value="shared")
    first_resolution_id = deterministic_id(
        "entity-resolution",
        first.entity_id,
        external.namespace,
        external.value,
        "exact_external_id",
        "accepted",
    )
    second_resolution_id = deterministic_id(
        "entity-resolution",
        second.entity_id,
        external.namespace,
        external.value,
        "exact_external_id",
        "accepted",
    )
    model = WorldModel()
    model.add_many(
        [
            first,
            second,
            EntityResolution(
                resolution_id=first_resolution_id,
                entity_id=first.entity_id,
                external_identifier=external,
                method=ResolutionMethod.EXACT_EXTERNAL_ID,
                decision=ResolutionDecision.ACCEPTED,
                score=1.0,
                resolver="test",
                resolved_at=NOW,
            ),
        ]
    )
    with pytest.raises(ValueError, match="already resolves"):
        model.add(
            EntityResolution(
                resolution_id=second_resolution_id,
                entity_id=second.entity_id,
                external_identifier=external,
                method=ResolutionMethod.EXACT_EXTERNAL_ID,
                decision=ResolutionDecision.ACCEPTED,
                score=1.0,
                resolver="test",
                resolved_at=NOW,
            )
        )


def test_entity_cascade_removes_capability_backed_service() -> None:
    owner = entity("Owner", EntityType.POWER_PLANT)
    consumer = entity("Consumer", EntityType.FACILITY)
    capability_id = deterministic_id(
        "capability", owner.entity_id, CapabilityKind.POWER.value, "generation"
    )
    capability = Capability(
        capability_id=capability_id,
        name="Generation",
        kind=CapabilityKind.POWER,
        nominal_capacity=Quantity(value=Decimal(100), unit="MW"),
        owner=owner.ref(),
    )
    service_id = deterministic_id("service", "seraph", "generation")
    service = Service(
        service_id=service_id,
        name="Generation",
        provider_entity_ids=(owner.entity_id,),
        capability_ids=(capability_id,),
    )
    model = WorldModel()
    model.add_many([owner, consumer, capability, service])
    model.remove_entity(owner.entity_id, cascade=True)
    assert capability_id not in model.capabilities
    assert service_id not in model.services


def test_world_snapshot_counts_are_immutable() -> None:
    snapshot = WorldModel().snapshot()
    with pytest.raises(TypeError):
        snapshot.counts["entities"] = 99  # type: ignore[index]


def test_world_model_rejects_conflicting_resolution_state_on_construction() -> None:
    first = entity("Direct First")
    second = entity("Direct Second")
    external = ExternalIdentifier(namespace="demo-direct", value="shared")
    resolutions = [
        EntityResolution(
            resolution_id=deterministic_id(
                "entity-resolution",
                subject.entity_id,
                external.namespace,
                external.value,
                "manual",
                "accepted",
            ),
            entity_id=subject.entity_id,
            external_identifier=external,
            method=ResolutionMethod.MANUAL,
            decision=ResolutionDecision.ACCEPTED,
            score=1.0,
            resolver="test",
            resolved_at=NOW,
        )
        for subject in (first, second)
    ]
    with pytest.raises(ValueError, match="multiple entities"):
        WorldModel(
            entities={first.entity_id: first, second.entity_id: second},
            resolutions={item.resolution_id: item for item in resolutions},
        )


def test_accepted_resolution_takes_precedence_over_ambiguous_direct_identifiers() -> None:
    first = entity("Direct Candidate A")
    second = entity("Direct Candidate B")
    external = ExternalIdentifier(namespace="shared", value="id-1")
    first = first.model_copy(update={"external_identifiers": (external,)})
    second = second.model_copy(update={"external_identifiers": (external,)})
    resolution_id = deterministic_id(
        "entity-resolution",
        second.entity_id,
        external.namespace,
        external.value,
        "manual",
        "accepted",
    )
    resolution = EntityResolution(
        resolution_id=resolution_id,
        entity_id=second.entity_id,
        external_identifier=external,
        method=ResolutionMethod.MANUAL,
        decision=ResolutionDecision.ACCEPTED,
        score=1.0,
        resolver="test",
        resolved_at=NOW,
    )
    model = WorldModel()
    model.add_many([first, second, resolution])
    assert model.find_entity_by_external_identifier("shared", "id-1") == (second.entity_id,)


def test_ontology_rejects_affine_measurement_for_capacity_and_flow() -> None:
    owner = entity("Thermal Owner", EntityType.FACILITY)
    capacity_id = deterministic_id(
        "capability", owner.entity_id, CapabilityKind.PROCESSING.value, "temperature"
    )
    with pytest.raises(ValueError, match="non-affine"):
        Capability(
            capability_id=capacity_id,
            name="Temperature",
            kind=CapabilityKind.PROCESSING,
            nominal_capacity=Quantity(value=Decimal(20), unit="Cel"),
            owner=owner.ref(),
        )

    target = entity("Thermal Target")
    flow_id = deterministic_id(
        "flow",
        FlowKind.OTHER.value,
        owner.entity_id,
        target.entity_id,
        "20",
        "Cel",
        NOW.isoformat(),
        END.isoformat(),
    )
    with pytest.raises(ValueError, match="non-affine"):
        Flow(
            flow_id=flow_id,
            flow_type=FlowKind.OTHER,
            source=owner.ref(),
            target=target.ref(),
            quantity=Quantity(value=Decimal(20), unit="Cel"),
            valid_time=WINDOW,
        )
