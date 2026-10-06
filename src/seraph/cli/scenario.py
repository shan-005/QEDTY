from __future__ import annotations

from datetime import UTC, datetime, timedelta

from seraph.continuity.engine import ContinuityEngine
from seraph.core.enums import (
    EntityType,
    EpistemicStatus,
    EventType,
    InterventionType,
    RelationshipType,
)
from seraph.core.hash import deterministic_id
from seraph.graph.store import TemporalGraph
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship
from seraph.propagation.engine import PropagationEngine
from seraph.scenarios.models import Intervention
from seraph.scenarios.shocks import Shock


def demo_payload() -> dict:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=24)
    names = [
        ("sat", EntityType.SATELLITE),
        ("pnt", EntityType.GNSS_SERVICE),
        ("telecom", EntityType.TELECOM_NETWORK),
        ("payments", EntityType.PAYMENT_SYSTEM),
        ("digital", EntityType.SERVICE),
    ]
    ents = [
        Entity(
            entity_id=deterministic_id("entity", "seraph", t.value, n),
            entity_type=t,
            canonical_name=n.title(),
            namespace="seraph",
            epistemic_status=EpistemicStatus.OBSERVED if n == "sat" else EpistemicStatus.DERIVED,
            confidence=0.98,
        )
        for n, t in names
    ]
    g = TemporalGraph()
    [g.add_entity(e) for e in ents]
    for a, b, w in zip(ents, ents[1:], [0.95, 0.9, 0.8, 0.85], strict=False):
        r = Relationship(
            relationship_id=deterministic_id(
                "rel",
                a.entity_id,
                b.entity_id,
                RelationshipType.SUPPORTS.value,
                start.isoformat(),
                end.isoformat(),
            ),
            source={"entity_id": a.entity_id},
            target={"entity_id": b.entity_id},
            relationship_type=RelationshipType.SUPPORTS,
            valid_from=start,
            valid_to=end,
            observed_at=start,
            strength=w,
            capacity_fraction=1,
            epistemic_status=EpistemicStatus.DERIVED,
        )
        g.add_relationship(r)
    shock = Shock(
        shock_id=deterministic_id(
            "shock",
            "GNSS degradation",
            EventType.GNSS_INTERFERENCE.value,
            ents[0].entity_id,
            start.isoformat(),
            end.isoformat(),
            0.6,
        ),
        name="GNSS degradation",
        event_type=EventType.GNSS_INTERFERENCE,
        source_entity_id=ents[0].entity_id,
        starts_at=start,
        ends_at=end,
        severity=0.6,
    )
    prop = PropagationEngine(g).propagate(shock)
    cont = ContinuityEngine().simulate(ents[-1].entity_id, shock, prop)
    intervention = Intervention(
        intervention_id="demo-backup",
        name="Backup timing",
        intervention_type=InterventionType.BACKUP_SERVICE,
        cost_usd=1_000_000,
        protected_entity_ids=(ents[-1].entity_id,),
        transmission_reduction=0.5,
    )
    cf = PropagationEngine(g).propagate(shock, transmission_reduction={ents[-1].entity_id: 0.5})
    cfc = ContinuityEngine().simulate(ents[-1].entity_id, shock, cf)
    return {
        "product": "SERAPH-PCI-X",
        "nodes": len(g.entities()),
        "relationships": len(g.relationships()),
        "path_hops": len(
            g.shortest_paths(ents[0].entity_id, ents[-1].entity_id, at=start)[0].relationship_ids
        ),
        "baseline_capacity": cont.minimum_capacity_fraction,
        "counterfactual_capacity": cfc.minimum_capacity_fraction,
        "continuity_gain": cfc.minimum_capacity_fraction - cont.minimum_capacity_fraction,
        "intervention_cost_usd": intervention.cost_usd,
        "status": "modeled_demo",
    }
