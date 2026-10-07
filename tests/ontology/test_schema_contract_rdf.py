from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_jsonld_context_covers_core_terms() -> None:
    context = json.loads((ROOT / "contracts/rdf/context.jsonld").read_text(encoding="utf-8"))[
        "@context"
    ]
    for term in (
        "Entity",
        "Relationship",
        "Event",
        "Capability",
        "Service",
        "Flow",
        "Assertion",
        "EntityResolution",
        "entityId",
        "canonicalName",
        "validTime",
        "observedAt",
        "confidence",
    ):
        assert term in context


def test_turtle_contract_has_expected_ontology_surface() -> None:
    ttl = (ROOT / "contracts/rdf/seraph-ontology.ttl").read_text(encoding="utf-8")
    assert "seraph: a owl:Ontology" in ttl
    for term in (
        "Entity",
        "Relationship",
        "Event",
        "Capability",
        "Service",
        "Flow",
        "Assertion",
        "EntityResolution",
    ):
        assert f"seraph:{term} a owl:Class" in ttl
    assert "prov:Entity" in ttl
    assert "prov:Activity" in ttl
