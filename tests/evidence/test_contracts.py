from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "evidence" / "json-schema" / "evidence.schema.json"


def test_evidence_schema_is_draft_2020_12() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_golden_record_validates_against_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    record = json.loads(
        (ROOT / "data/contracts/golden-vectors/evidence/record.json").read_text(
            encoding="utf-8-sig"
        )
    )
    errors = list(Draft202012Validator(schema).iter_errors(record))
    assert errors == []


def test_rdf_and_shacl_contracts_have_expected_standard_terms() -> None:
    rdf = (ROOT / "contracts/evidence/rdf/evidence.ttl").read_text(encoding="utf-8-sig")
    shacl = (ROOT / "contracts/evidence/shacl/evidence.shacl.ttl").read_text(encoding="utf-8-sig")
    assert "prov:Entity" in rdf
    assert "prov:Activity" in rdf
    assert "dqv:QualityMeasurement" in rdf
    assert "dcat:Distribution" in rdf
    assert "oa:Annotation" in rdf
    assert "sh:NodeShape" in shacl
    assert "sh:ValidationReport" not in shacl


def test_protobuf_contract_surface() -> None:
    proto = (ROOT / "proto/qedty/evidence/v1/evidence.proto").read_text(encoding="utf-8-sig")
    for message in (
        "SourceRef",
        "EntityRef",
        "ProvenanceRef",
        "TimeWindow",
        "EvidenceSelector",
        "AcquisitionReceipt",
        "QualityMeasurement",
        "EvidenceRecord",
    ):
        assert f"message {message} " in proto
