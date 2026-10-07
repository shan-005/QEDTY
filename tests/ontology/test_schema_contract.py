from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from seraph.core.enums import EntityType
from seraph.core.hash import deterministic_id
from seraph.ontology.entities import Entity

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_SCHEMA_PATH = ROOT / "contracts/json-schema/ontology.schema.json"
ARROW_CONTRACT_PATH = ROOT / "contracts/arrow/ontology.contract.json"
PROTO_PATH = ROOT / "proto/seraph/ontology/v1/ontology.proto"


def test_ontology_schema_is_valid_and_refs_are_closed() -> None:
    schema = json.loads(ONTOLOGY_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    definitions = schema["$defs"]
    for property_schema in schema["properties"].values():
        if property_schema.get("type") == "array":
            ref = property_schema["items"]["$ref"]
            assert ref.removeprefix("#/$defs/") in definitions

    entity_id = deterministic_id("entity", "seraph", "satellite", "demo")
    document = {
        "schema": "seraph-world-model@1.0.0",
        "ontology_profile": "seraph-ontology@2.0.0",
        "version": 1,
        "entities": [
            Entity(
                entity_id=entity_id,
                entity_type=EntityType.SATELLITE,
                canonical_name="Demo",
            ).model_dump(mode="json")
        ],
        "relationships": [],
        "events": [],
        "capabilities": [],
        "services": [],
        "flows": [],
        "assertions": [],
        "resolutions": [],
    }
    Draft202012Validator(schema).validate(document)


def test_arrow_contract_has_every_ontology_record_type() -> None:
    contract = json.loads(ARROW_CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["contract"] == "seraph-ontology-arrow@1"
    assert set(contract["record_batches"]) == {
        "entities",
        "relationships",
        "events",
        "capabilities",
        "services",
        "flows",
        "assertions",
        "resolutions",
    }


def test_protobuf_contract_declares_every_ontology_record() -> None:
    proto = PROTO_PATH.read_text(encoding="utf-8")
    for message in (
        "Entity",
        "EntityResolution",
        "Relationship",
        "WorldEvent",
        "Capability",
        "Service",
        "Flow",
        "Assertion",
        "OntologyDocument",
    ):
        assert f"message {message} " in proto
