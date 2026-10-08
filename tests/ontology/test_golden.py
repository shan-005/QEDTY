from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from qedty.core.enums import EntityType, EpistemicStatus, EventType, RelationshipType
from qedty.core.hash import deterministic_id
from qedty.core.types import EntityRef, TimeWindow
from qedty.core.units import Quantity
from qedty.ontology.assertions import Assertion
from qedty.ontology.capabilities import Capability
from qedty.ontology.entities import Entity
from qedty.ontology.events import WorldEvent
from qedty.ontology.flows import Flow
from qedty.ontology.relations import Relationship
from qedty.ontology.services import Service
from qedty.ontology.terms import AssertionKind, CapabilityKind, FlowKind

ROOT = Path(__file__).resolve().parents[2]
VROOT = ROOT / "data/contracts/golden-vectors/ontology"
NOW = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, 1, tzinfo=UTC)
WINDOW = TimeWindow(start=NOW, end=END)


def vector(name: str) -> dict[str, object]:
    payload = json.loads((VROOT / name).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError(f"golden vector must be an object: {name}")
    return cast("dict[str, object]", payload)


def test_entity_vector() -> None:
    v = vector("entity.json")
    item = Entity(
        entity_id=str(v["entity_id"]),
        entity_type=EntityType(str(v["entity_type"])),
        canonical_name=str(v["canonical_name"]),
        namespace=str(v["namespace"]),
    )
    assert item.entity_id == deterministic_id(
        "entity", item.namespace, item.entity_type.value, item.canonical_name.casefold()
    )


def test_relationship_vector() -> None:
    v = vector("relationship.json")
    item = Relationship(
        relationship_id=str(v["relationship_id"]),
        source=EntityRef(entity_id=str(v["source_id"])),
        target=EntityRef(entity_id=str(v["target_id"])),
        relationship_type=RelationshipType(str(v["relationship_type"])),
    )
    assert item.relationship_id == str(v["relationship_id"])


def test_event_vector() -> None:
    v = vector("event.json")
    item = WorldEvent(
        event_id=str(v["event_id"]),
        event_type=EventType(str(v["event_type"])),
        name=str(v["name"]),
        time=TimeWindow(start=NOW, end=END),
        severity=float(v["severity"]),
    )
    assert item.event_id == str(v["event_id"])


def test_flow_vector() -> None:
    v = vector("flow.json")
    q = v["quantity"]
    assert isinstance(q, dict)
    item = Flow(
        flow_id=str(v["flow_id"]),
        flow_type=FlowKind(str(v["flow_type"])),
        source=EntityRef(entity_id=str(v["source_id"])),
        target=EntityRef(entity_id=str(v["target_id"])),
        quantity=Quantity(value=Decimal(str(q["value"])), unit=str(q["unit"])),
        valid_time=WINDOW,
    )
    assert item.flow_id == str(v["flow_id"])


def test_capability_vector() -> None:
    v = vector("capability.json")
    q = v["nominal_capacity"]
    assert isinstance(q, dict)
    item = Capability(
        capability_id=str(v["capability_id"]),
        name=str(v["name"]),
        kind=CapabilityKind(str(v["kind"])),
        nominal_capacity=Quantity(value=Decimal(str(q["value"])), unit=str(q["unit"])),
        owner=EntityRef(entity_id=str(v["owner_id"])),
    )
    assert item.capability_id == str(v["capability_id"])


def test_service_vector() -> None:
    v = vector("service.json")
    item = Service(
        service_id=str(v["service_id"]),
        name=str(v["name"]),
        namespace=str(v["namespace"]),
        provider_entity_ids=tuple(str(x) for x in v["provider_entity_ids"]),
    )
    assert item.service_id == str(v["service_id"])


def test_assertion_vector() -> None:
    v = vector("assertion.json")
    item = Assertion(
        assertion_id=str(v["assertion_id"]),
        subject=EntityRef(entity_id=str(v["subject_id"])),
        predicate=str(v["predicate"]),
        value=v["value"],
        kind=AssertionKind(str(v["kind"])),
        asserted_at=NOW,
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    assert item.assertion_id == str(v["assertion_id"])
