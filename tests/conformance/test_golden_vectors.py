from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_core_contract_schema_is_self_validating() -> None:
    path = ROOT / "contracts" / "json-schema" / "core.contract.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)


def test_arrow_contract_matches_python_field_contract() -> None:
    descriptor = json.loads(
        (ROOT / "contracts" / "arrow" / "core.contract.json").read_text(encoding="utf-8-sig")
    )
    names = [field["name"] for field in descriptor["fields"]]
    assert names == [
        "value_json",
        "epistemic_state",
        "evidence_ids",
        "provenance_ids",
        "assumptions",
        "model_id",
        "model_version",
        "valid_at",
        "uncertainty_json",
        "metadata_json",
    ]


def test_proto_contract_contains_required_messages() -> None:
    proto = (ROOT / "proto" / "qedty" / "core" / "v1" / "core.proto").read_text(
        encoding="utf-8-sig"
    )
    for message in (
        "EntityRef",
        "TimeWindow",
        "ExternalIdentifier",
        "Quantity",
        "ContractResult",
        "RunResult",
    ):
        assert f"message {message} " in proto
