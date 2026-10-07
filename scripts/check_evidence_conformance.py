from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from seraph.core.types import EntityRef, ProvenanceRef, SourceRef, TimeWindow  # noqa: E402
from seraph.evidence import (  # noqa: E402
    AcquisitionMethod,
    AcquisitionRequest,
    DataQuality,
    EvidenceKind,
    EvidenceRecord,
    EvidenceSelector,
    LicensePolicy,
    PermissionState,
    ProvenanceActivity,
    QualityDimension,
    QualityMeasurement,
    SelectorType,
    make_receipt,
    normalize_record,
)

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "data/contracts/golden-vectors/evidence"
SCHEMA = json.loads(
    (ROOT / "contracts/evidence/json-schema/evidence.schema.json").read_text(encoding="utf-8")
)


def main() -> None:
    for path in sorted(VECTORS.glob("*.json")):
        vector = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "record.json":
            Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(vector)
            EvidenceRecord.model_validate_json(path.read_bytes())
        elif path.name == "acquisition.json":
            from seraph.evidence.acquisition import AcquisitionReceipt
            AcquisitionReceipt.model_validate_json(path.read_bytes())
        elif path.name == "quality.json":
            DataQuality.model_validate_json(path.read_bytes())
        elif path.name == "provenance.json":
            ProvenanceActivity.model_validate_json(path.read_bytes())
        elif path.name == "selector.json":
            EvidenceSelector.model_validate_json(path.read_bytes())
        elif path.name == "license.json":
            LicensePolicy.model_validate_json(path.read_bytes())
        elif path.name == "acquisition_request.json":
            AcquisitionRequest.model_validate_json(path.read_bytes())
        elif path.name == "normalization.json":
            normalized = normalize_record("demo-source", "row-1", {" Name ": "  Demo  ", "value": 3})
            assert vector["normalized_digest"] == normalized.normalized_digest
            assert vector["record_digest"] == normalized.record_digest
        print(f"PASS {path.relative_to(ROOT)}")
    source_uri = "https://example.test/evidence"
    content = b'{"hello":"seraph"}'
    now = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
    request = AcquisitionRequest(
        method=AcquisitionMethod.HTTPS, requested_uri=source_uri, requested_at=now
    )
    receipt = make_receipt(
        request,
        final_uri=source_uri,
        retrieved_at=now,
        content=content,
        status_code=200,
        response_media_type="application/json",
    )
    item = EvidenceRecord.from_content(
        source=SourceRef(source_id="demo-source"),
        source_uri=source_uri,
        content=content,
        retrieved_at=now,
        kind=EvidenceKind.API_RESPONSE,
        observed_at=now + timedelta(minutes=1),
        valid_time=TimeWindow(start=now, end=now + timedelta(hours=1)),
        acquisition=receipt, about_entities=(EntityRef(entity_id="entity:demo"),),
        selectors=(EvidenceSelector(selector_type=SelectorType.JSON_POINTER, value="/hello"),),
        provenance_ids=(ProvenanceRef(provenance_id="prov:demo"),),
    )
    assert item.evidence_id == json.loads((VECTORS / "record.json").read_text())["evidence_id"]
    quality = DataQuality(
        measurements=(
            QualityMeasurement(
                dimension=QualityDimension.COMPLETENESS,
                metric="x",
                value=0.5,
                method="m",
                measured_at=now,
            ),
        )
    )
    assert quality.weighted_score({QualityDimension.COMPLETENESS: 1}) == 0.5
    assert (
        make_receipt(request, final_uri=source_uri, retrieved_at=now, content=content).content_sha256
        == item.content_sha256
    )
    print("PASS evidence cross-checks")


if __name__ == "__main__":
    main()
