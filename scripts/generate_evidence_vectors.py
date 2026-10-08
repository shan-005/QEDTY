from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qedty.core.types import EntityRef, ProvenanceRef, SourceRef, TimeWindow
from qedty.evidence import (
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
    Redistribution,
    SelectorType,
    make_receipt,
    normalize_record,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "contracts" / "golden-vectors" / "evidence"
NOW = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def write(name: str, payload: dict[str, object]) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = AcquisitionRequest(
        method=AcquisitionMethod.HTTPS,
        requested_uri="https://example.test/evidence",
        requested_at=NOW,
        headers=(("Accept", "application/json"),),
    )
    content = b'{"hello":"qedty"}'
    receipt = make_receipt(
        request,
        final_uri=request.requested_uri,
        retrieved_at=NOW,
        content=content,
        status_code=200,
        response_media_type="application/json",
    )
    item = EvidenceRecord.from_content(
        source=SourceRef(source_id="demo-source"),
        source_uri=request.requested_uri,
        content=content,
        retrieved_at=NOW,
        title="Demo evidence",
        kind=EvidenceKind.API_RESPONSE,
        observed_at=NOW + timedelta(minutes=1),
        valid_time=TimeWindow(start=NOW, end=NOW + timedelta(hours=1)),
        acquisition=receipt,
        about_entities=(EntityRef(entity_id="entity:demo"),),
        selectors=(EvidenceSelector(selector_type=SelectorType.JSON_POINTER, value="/hello"),),
        provenance_ids=(ProvenanceRef(provenance_id="prov:demo"),),
        license_policy=LicensePolicy(
            spdx_expression="CC-BY-4.0",
            commercial_use=PermissionState.ALLOWED,
            attribution_required=True,
            redistribution=Redistribution.ATTRIBUTION,
            source_url="https://example.test/license",
        ),
        metadata={"format": "json"},
    )
    quality = DataQuality(
        measurements=(
            QualityMeasurement(
                dimension=QualityDimension.COMPLETENESS,
                metric="required-field-coverage",
                value=0.95,
                method="present/expected",
                measured_at=NOW,
            ),
        )
    )
    prov = ProvenanceActivity.create(
        activity="normalize",
        agent="qedty",
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=5),
        parameters={"profile": "qedty-normalization@1"},
        used_evidence_ids=(item.evidence_id,),
        generated_evidence_ids=(item.evidence_id,),
        software_name="qedty",
        software_version="0.1a0",
    )
    normalized = normalize_record("demo-source", "row-1", {" Name ": "  Demo  ", "value": 3})

    write("record.json", item.model_dump(mode="json"))
    write("acquisition.json", receipt.model_dump(mode="json"))
    write("quality.json", quality.model_dump(mode="json"))
    write("provenance.json", prov.model_dump(mode="json"))
    write(
        "selector.json",
        EvidenceSelector(
            selector_type=SelectorType.BYTE_RANGE, start=2, end=7, unit="bytes"
        ).model_dump(mode="json"),
    )
    write(
        "normalization.json",
        {
            "source_name": normalized.source_name,
            "record_id": normalized.record_id,
            "normalized_digest": normalized.normalized_digest,
            "record_digest": normalized.record_digest,
            "attributes": normalized.attributes,
        },
    )
    write("license.json", item.license_policy.model_dump(mode="json"))
    write("acquisition_request.json", request.model_dump(mode="json"))


if __name__ == "__main__":
    main()
