from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from qedty.evidence.models import EvidenceRecord

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "contracts" / "evidence" / "field-mapping.json"
JSON_SCHEMA_PATH = ROOT / "contracts" / "evidence" / "json-schema" / "evidence.schema.json"
ARROW_PATH = ROOT / "contracts" / "evidence" / "arrow" / "schema.json"
PROTO_PATH = ROOT / "proto" / "qedty" / "evidence" / "v1" / "evidence.proto"
RDF_PATH = ROOT / "contracts" / "evidence" / "rdf" / "evidence.ttl"
SHACL_PATH = ROOT / "contracts" / "evidence" / "shacl" / "evidence.shacl.ttl"

ALLOWED_STATUSES = {"direct", "renamed", "transformed", "partial", "omitted", "shape_only"}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(value, dict)
    return value


def _proto_message_fields(source: str, message_name: str) -> set[str]:
    match = re.search(
        rf"\bmessage\s+{re.escape(message_name)}\s*\{{(.*?)\}}",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing Protobuf message {message_name}"
    field_pattern = re.compile(
        r"^\s*(?:(?:repeated|optional)\s+)?[A-Za-z_]\w*(?:<[^>]+>)?(?:\.[A-Za-z_]\w*)*\s+(\w+)\s*=\s*\d+\s*;",
        flags=re.MULTILINE,
    )
    return {field for field in field_pattern.findall(match.group(1))}


def _representation_fields(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    raise AssertionError(f"invalid mapped representation: {value!r}")


def test_mapping_covers_exact_python_and_json_schema_fields() -> None:
    mapping = _read_json(MAPPING_PATH)
    schema = _read_json(JSON_SCHEMA_PATH)
    fields = mapping["fields"]
    names = [item["semantic_field"] for item in fields]

    assert mapping["profile"] == "qedty-evidence-field-mapping@1"
    assert len(names) == len(set(names)), "duplicate semantic field mapping"
    assert set(names) == set(EvidenceRecord.model_fields)
    assert set(schema["properties"]) == set(EvidenceRecord.model_fields)

    for item in fields:
        name = item["semantic_field"]
        assert item["python"] == f"EvidenceRecord.{name}"
        assert item["json_schema"] == {"status": "direct", "field": name}
        assert name in schema["properties"]


def test_arrow_projection_mapping_matches_declared_columns() -> None:
    mapping = _read_json(MAPPING_PATH)
    arrow = _read_json(ARROW_PATH)
    columns = {item["name"] for item in arrow["columns"]}

    for item in mapping["fields"]:
        surface = item["arrow"]
        assert surface["status"] in ALLOWED_STATUSES
        names = _representation_fields(surface["field"])
        if surface["status"] == "omitted":
            assert not names, item["semantic_field"]
        else:
            assert names, item["semantic_field"]
            assert names <= columns, (item["semantic_field"], names - columns)
        if surface["status"] in {"renamed", "transformed", "partial"}:
            assert surface.get("notes"), item["semantic_field"]


def test_protobuf_projection_mapping_matches_evidence_record_fields() -> None:
    mapping = _read_json(MAPPING_PATH)
    proto = PROTO_PATH.read_text(encoding="utf-8-sig")
    fields = _proto_message_fields(proto, "EvidenceRecord")

    for item in mapping["fields"]:
        surface = item["protobuf"]
        assert surface["status"] in ALLOWED_STATUSES
        name_set = _representation_fields(surface["field"])
        if surface["status"] == "omitted":
            assert not name_set, item["semantic_field"]
        else:
            assert name_set, item["semantic_field"]
            assert name_set <= fields, (item["semantic_field"], name_set - fields)
        if surface["status"] in {"renamed", "transformed", "partial"}:
            assert surface.get("notes"), item["semantic_field"]


def test_rdf_shacl_mapping_never_overstates_current_coverage() -> None:
    mapping = _read_json(MAPPING_PATH)
    rdf = RDF_PATH.read_text(encoding="utf-8-sig")
    shacl = SHACL_PATH.read_text(encoding="utf-8-sig")
    combined = f"{rdf}\n{shacl}"

    shape_only = {
        item["semantic_field"]: set(item["rdf_shacl"]["terms"])
        for item in mapping["fields"]
        if item["rdf_shacl"]["status"] == "shape_only"
    }
    assert shape_only == {
        "evidence_id": {"ser:evidenceId"},
        "source_uri": {"ser:sourceUri"},
        "content_sha256": {"ser:contentSha256"},
    }
    for item in mapping["fields"]:
        surface = item["rdf_shacl"]
        assert surface["status"] in ALLOWED_STATUSES
        terms = surface["terms"]
        assert isinstance(terms, list)
        if surface["status"] == "omitted":
            assert terms == [], item["semantic_field"]
        else:
            assert terms, item["semantic_field"]
            for term in terms:
                assert term in combined, (item["semantic_field"], term)
        if surface["status"] in {"partial", "shape_only"}:
            assert surface.get("notes"), item["semantic_field"]

    # The current shapes explicitly constrain only these three EvidenceRecord fields.
    declared = set(re.findall(r"sh:path\s+([A-Za-z_][\w]*:[A-Za-z_]\w*)", shacl))
    assert declared == {"ser:evidenceId", "ser:contentSha256", "ser:sourceUri"}


def test_nested_lossy_or_missing_mappings_are_explicit() -> None:
    mapping = _read_json(MAPPING_PATH)
    gaps = {item["path"]: item for item in mapping["known_nested_gaps"]}
    assert {
        "acquisition.response_headers",
        "quality",
        "license_policy",
        "metadata",
    } <= set(gaps)
    assert gaps["acquisition.response_headers"]["status"] == "potentially_lossy"
    assert gaps["quality"]["status"] == "partial"
    assert gaps["license_policy"]["status"] == "omitted"
    assert gaps["metadata"]["status"] == "serialized_json"
