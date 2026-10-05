from __future__ import annotations

from datetime import datetime, timedelta, timezone

from seraph.pci.core.enums import EntityType, EpistemicStatus, RelationshipType, ShockType, InterventionType
from seraph.pci.core.ids import deterministic_id
from seraph.pci.core.types import EntityRef, Relationship
from seraph.pci.counterfactual import CounterfactualEngine, Intervention
from seraph.pci.continuity import ContinuityEngine
from seraph.pci.economics import EconomicExposure, EconomicLossEngine
from seraph.pci.entities.models import Entity
from seraph.pci.graph.builder import GraphBuilder
from seraph.pci.graph.store import TemporalGraph
from seraph.pci.optimization import ResilienceOptimizer
from seraph.pci.shocks import Shock, ShockPropagator

UTC = timezone.utc


def build_demo_graph() -> TemporalGraph:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=365)
    entities = [
        Entity(
            entity_id=deterministic_id("entity", "seraph", EntityType.SATELLITE.value, "gnss gps constellation"),
            entity_type=EntityType.SATELLITE,
            canonical_name="GNSS GPS Constellation",
            namespace="seraph",
            epistemic_status=EpistemicStatus.OBSERVED,
            confidence=1.0,
        ),
        Entity(
            entity_id=deterministic_id("entity", "seraph", EntityType.GNSS_SERVICE.value, "global pnt service"),
            entity_type=EntityType.GNSS_SERVICE,
            canonical_name="Global PNT Service",
            namespace="seraph",
            epistemic_status=EpistemicStatus.DERIVED,
            confidence=0.95,
        ),
        Entity(
            entity_id=deterministic_id("entity", "seraph", EntityType.TELECOM_NETWORK.value, "telecom timing network"),
            entity_type=EntityType.TELECOM_NETWORK,
            canonical_name="Telecom Timing Network",
            namespace="seraph",
            epistemic_status=EpistemicStatus.DERIVED,
            confidence=0.90,
        ),
        Entity(
            entity_id=deterministic_id("entity", "seraph", EntityType.PAYMENT_SYSTEM.value, "payment settlement infrastructure"),
            entity_type=EntityType.PAYMENT_SYSTEM,
            canonical_name="Payment Settlement Infrastructure",
            namespace="seraph",
            epistemic_status=EpistemicStatus.DERIVED,
            confidence=0.85,
        ),
        Entity(
            entity_id=deterministic_id("entity", "seraph", EntityType.ECONOMIC_FUNCTION.value, "digital payments"),
            entity_type=EntityType.ECONOMIC_FUNCTION,
            canonical_name="Digital Payments",
            namespace="seraph",
            epistemic_status=EpistemicStatus.DERIVED,
            confidence=0.85,
        ),
    ]
    by_name = {entity.canonical_name: entity for entity in entities}
    refs = {name: EntityRef(entity_id=entity.entity_id) for name, entity in by_name.items()}
    def rel(source: Entity, target: Entity, kind: RelationshipType, confidence: float, weight: float) -> Relationship:
        rid = deterministic_id("rel", source.entity_id, target.entity_id, kind.value, start.isoformat(), end.isoformat())
        return Relationship(
            relationship_id=rid,
            source=EntityRef(entity_id=source.entity_id),
            target=EntityRef(entity_id=target.entity_id),
            relationship_type=kind,
            valid_from=start,
            valid_to=end,
            observed_at=start,
            confidence=confidence,
            weight=weight,
            epistemic_status=EpistemicStatus.DERIVED,
        )
    relationships = [
        rel(by_name["GNSS GPS Constellation"], by_name["Global PNT Service"], RelationshipType.PROVIDES, 0.99, 0.95),
        rel(by_name["Global PNT Service"], by_name["Telecom Timing Network"], RelationshipType.SUPPORTS, 0.95, 0.90),
        rel(by_name["Telecom Timing Network"], by_name["Payment Settlement Infrastructure"], RelationshipType.TIMES, 0.90, 0.80),
        rel(by_name["Payment Settlement Infrastructure"], by_name["Digital Payments"], RelationshipType.ENABLES, 0.90, 0.85),
    ]
    builder = GraphBuilder()
    for entity in entities:
        builder.add_entity(entity)
    for relationship in relationships:
        builder.add_relationship(relationship)
    return builder.build()


def run_demo() -> dict[str, object]:
    graph = build_demo_graph()
    names = {entity.canonical_name: entity for entity in graph.entities()}
    source = names["GNSS GPS Constellation"]
    target = names["Digital Payments"]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=24)
    shock = Shock(
        shock_id=deterministic_id("shock", "GNSS degradation", ShockType.GNSS_INTERFERENCE.value, source.entity_id, start.isoformat(), end.isoformat(), 0.60),
        name="GNSS degradation",
        shock_type=ShockType.GNSS_INTERFERENCE,
        source_entity_id=source.entity_id,
        start=start,
        end=end,
        severity=0.60,
    )
    propagator = ShockPropagator(graph)
    continuity_engine = ContinuityEngine()
    events = propagator.propagate(shock)
    continuity = continuity_engine.simulate(entity_id=target.entity_id, shock=shock, events=events)
    exposure = EconomicExposure(entity_id=target.entity_id, reference_value_usd=10_000_000.0, exposed_fraction=0.50)
    loss = EconomicLossEngine().estimate(exposure=exposure, continuity=continuity, duration_hours=shock.duration_hours)
    intervention = Intervention(
        intervention_id="synthetic-backup-timing",
        name="Backup timing service",
        intervention_type=InterventionType.BACKUP_SERVICE,
        cost_usd=1_000_000.0,
        protected_entities=(target.entity_id,),
        transmission_reduction=0.50,
    )
    cf = CounterfactualEngine(propagator, continuity_engine).compare(shock=shock, entity_id=target.entity_id, intervention=intervention)
    ranking = ResilienceOptimizer(CounterfactualEngine(propagator, continuity_engine)).rank(
        shock=shock, entity_id=target.entity_id, interventions=(intervention,)
    )
    return {
        "nodes": graph.snapshot().entity_count,
        "relationships": graph.snapshot().relationship_count,
        "path_hops": len(graph.shortest_paths(source.entity_id, target.entity_id, at=start)[0].relationship_ids),
        "minimum_capacity_fraction": continuity.minimum_capacity_fraction,
        "modeled_loss_usd": loss.modeled_loss_usd,
        "counterfactual_continuity_gain": cf.continuity_gain,
        "best_rank_score": ranking.recommendations[0].rank_score,
    }
