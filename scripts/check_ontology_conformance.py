#!/usr/bin/env python3
"""Validate ontology golden vectors and interoperability contracts."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from qedty.core.enums import EntityType, EpistemicStatus, EventType, RelationshipType
from qedty.core.time import parse_rfc3339
from qedty.core.types import EntityRef, ExternalIdentifier, TimeWindow
from qedty.core.units import Quantity
from qedty.ontology import (
    Assertion,
    AssertionKind,
    Capability,
    CapabilityKind,
    Entity,
    EntityResolution,
    EventPhase,
    Flow,
    FlowKind,
    Relationship,
    ResolutionDecision,
    ResolutionMethod,
    Service,
    WorldEvent,
)

ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "data" / "contracts" / "golden-vectors" / "ontology"
SCHEMA_PATH = ROOT / "contracts" / "json-schema" / "ontology.schema.json"
ARROW_PATH = ROOT / "contracts" / "arrow" / "ontology.contract.json"
PROTO_PATH = ROOT / "proto" / "qedty" / "ontology" / "v1" / "ontology.proto"
RDF_PATH = ROOT / "contracts" / "rdf" / "qedty-ontology.ttl"
SHACL_PATH = ROOT / "contracts" / "shacl" / "qedty-ontology.shacl.ttl"

NOW = parse_rfc3339("2026-01-01T00:00:00+00:00")
END = parse_rfc3339("2026-01-01T01:00:00+00:00")
WINDOW = TimeWindow(start=NOW, end=END)


def load(name: str) -> dict[str, object]:
    payload = json.loads((VECTOR_DIR / name).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError(f"golden vector must be an object: {name}")
    return cast("dict[str, object]", payload)


def entity_from_vector(v: dict[str, object]) -> Entity:
    try:
        return Entity(
            entity_id=str(v["entity_id"]),
            entity_type=EntityType(str(v["entity_type"])),
            canonical_name=str(v["canonical_name"]),
            namespace=str(v["namespace"]),
        )
    except ValidationError:
        print(f"\n[!] HASH MISMATCH in {v.get('entity_id')}.")
        print("    Check the QEDTY namespace and the expected ontology identifiers.")
        print(
            "    Please update data/contracts/golden-vectors/ontology/entity.json with the new expected hash."
        )
        raise


def relationship_from_vector(v: dict[str, object]) -> Relationship:
    return Relationship(
        relationship_id=str(v["relationship_id"]),
        source=EntityRef(entity_id=str(v["source_id"])),
        target=EntityRef(entity_id=str(v["target_id"])),
        relationship_type=RelationshipType(str(v["relationship_type"])),
    )


def event_from_vector(v: dict[str, object]) -> WorldEvent:
    return WorldEvent(
        event_id=str(v["event_id"]),
        event_type=EventType(str(v["event_type"])),
        name=str(v["name"]),
        time=WINDOW,
        severity=float(v["severity"]),
        phase=EventPhase.UNKNOWN,
    )


def flow_from_vector(v: dict[str, object]) -> Flow:
    quantity = v["quantity"]
    if not isinstance(quantity, dict):
        raise TypeError("flow quantity vector must be an object")
    return Flow(
        flow_id=str(v["flow_id"]),
        flow_type=FlowKind(str(v["flow_type"])),
        source=EntityRef(entity_id=str(v["source_id"])),
        target=EntityRef(entity_id=str(v["target_id"])),
        quantity=Quantity(value=Decimal(str(quantity["value"])), unit=str(quantity["unit"])),
        valid_time=WINDOW,
    )


def capability_from_vector(v: dict[str, object]) -> Capability:
    quantity = v["nominal_capacity"]
    if not isinstance(quantity, dict):
        raise TypeError("capability quantity vector must be an object")
    return Capability(
        capability_id=str(v["capability_id"]),
        name=str(v["name"]),
        kind=CapabilityKind(str(v["kind"])),
        nominal_capacity=Quantity(
            value=Decimal(str(quantity["value"])), unit=str(quantity["unit"])
        ),
        owner=EntityRef(entity_id=str(v["owner_id"])),
    )


def service_from_vector(v: dict[str, object]) -> Service:
    return Service(
        service_id=str(v["service_id"]),
        name=str(v["name"]),
        namespace=str(v["namespace"]),
        provider_entity_ids=tuple(str(x) for x in v["provider_entity_ids"]),
    )


def assertion_from_vector(v: dict[str, object]) -> Assertion:
    return Assertion(
        assertion_id=str(v["assertion_id"]),
        subject=EntityRef(entity_id=str(v["subject_id"])),
        predicate=str(v["predicate"]),
        value=v["value"],
        kind=AssertionKind(str(v["kind"])),
        asserted_at=NOW,
        epistemic_status=EpistemicStatus.OBSERVED,
    )


def resolution_from_vector(v: dict[str, object]) -> EntityResolution:
    return EntityResolution(
        resolution_id=str(v["resolution_id"]),
        entity_id=str(v["entity_id"]),
        external_identifier=ExternalIdentifier(
            namespace=str(v["namespace"]),
            value=str(v["value"]),
        ),
        method=ResolutionMethod(str(v["method"])),
        decision=ResolutionDecision(str(v["decision"])),
        score=float(v["score"]),
        resolver=str(v["resolver"]),
        resolved_at=NOW,
    )


BUILDERS: dict[str, tuple[str, Callable[[dict[str, object]], BaseModel]]] = {
    "entities": ("entity.json", entity_from_vector),
    "relationships": ("relationship.json", relationship_from_vector),
    "events": ("event.json", event_from_vector),
    "flows": ("flow.json", flow_from_vector),
    "capabilities": ("capability.json", capability_from_vector),
    "services": ("service.json", service_from_vector),
    "assertions": ("assertion.json", assertion_from_vector),
    "resolutions": ("resolution.json", resolution_from_vector),
}


def build_document() -> dict[str, object]:
    document: dict[str, object] = {
        "schema": "qedty-world-model@1.0.0",
        "ontology_profile": "qedty-ontology@2.0.0",
        "version": 1,
        **{field: [] for field in BUILDERS},
    }
    for field, (filename, builder) in BUILDERS.items():
        item = builder(load(filename))
        document[field] = [item.model_dump(mode="json")]
    return document


def check_golden_vectors() -> None:
    for filename, builder in (value for value in BUILDERS.values()):
        builder(load(filename))
        print(f"PASS {VECTOR_DIR / filename}")


def check_json_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(build_document())
    print("PASS ontology JSON Schema 2020-12")


def check_arrow_contract() -> None:
    contract = json.loads(ARROW_PATH.read_text(encoding="utf-8-sig"))
    expected = set(BUILDERS)
    actual = set(contract["record_batches"])
    if actual != expected:
        raise AssertionError(f"Arrow record batches differ: {sorted(actual)}")
    print("PASS Arrow ontology contract")


def check_protobuf_surface() -> None:
    proto = PROTO_PATH.read_text(encoding="utf-8")
    messages = {
        "Entity",
        "EntityResolution",
        "Relationship",
        "WorldEvent",
        "Capability",
        "Service",
        "Flow",
        "Assertion",
        "OntologyDocument",
    }
    missing = sorted(f"message {name} " for name in messages if f"message {name} " not in proto)
    if missing:
        raise AssertionError(f"missing protobuf messages: {missing}")
    print("PASS Protobuf ontology contract surface")


def check_rdf_shacl_surface() -> None:
    rdf = RDF_PATH.read_text(encoding="utf-8")
    shacl = SHACL_PATH.read_text(encoding="utf-8")
    for name in (
        "Entity",
        "Relationship",
        "Event",
        "Capability",
        "Service",
        "Flow",
        "Assertion",
        "EntityResolution",
        "ExternalIdentifier",
        "TimeWindow",
        "Quantity",
        "GeodeticPoint",
    ):
        if f"qedty:{name}" not in rdf:
            raise AssertionError(f"RDF contract missing {name}")
    for name in (
        "EntityShape",
        "RelationshipShape",
        "EventShape",
        "CapabilityShape",
        "ServiceShape",
        "FlowShape",
        "AssertionShape",
        "EntityResolutionShape",
    ):
        if f"qedty:{name}" not in shacl:
            raise AssertionError(f"SHACL contract missing {name}")
    print("PASS RDF/SHACL ontology contract surface")


def main() -> int:
    check_golden_vectors()
    check_json_schema()
    check_arrow_contract()
    check_protobuf_surface()
    check_rdf_shacl_surface()
    print("PASS: ontology conformance and contract checks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
