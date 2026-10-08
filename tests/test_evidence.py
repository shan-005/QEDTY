from datetime import UTC, datetime, timedelta

from qedty.core.hash import deterministic_id
from qedty.core.types import EntityRef, SourceRef, TimeWindow
from qedty.evidence import (
    AcquisitionMethod,
    AcquisitionRequest,
    DataQuality,
    EvidenceAcquirer,
    EvidenceFileStore,
    EvidenceKind,
    EvidenceRecord,
    EvidenceRegistry,
    EvidenceSelector,
    QualityDimension,
    QualityMeasurement,
    SelectorType,
    make_receipt,
)


def test_evidence_identity_from_content() -> None:
    now = datetime(2026, 10, 6, 8, tzinfo=UTC)
    item = EvidenceRecord.from_content(
        source=SourceRef(source_id="demo"),
        source_uri="https://example.test/data",
        content=b"hello",
        retrieved_at=now,
        content_type="text/plain",
        kind=EvidenceKind.DOCUMENT,
    )
    assert item.evidence_id == deterministic_id(
        "evidence",
        item.source_uri,
        item.content_sha256,
        item.content_type,
        item.content_length_bytes,
        None,
    )
    assert item.content_address.startswith("sha256:")


def test_acquisition_recorder_emits_receipt() -> None:
    now = datetime(2026, 10, 6, 8, tzinfo=UTC)
    item = EvidenceAcquirer().record_bytes(
        "demo",
        "https://example.test/data",
        b"hello",
        retrieved_at=now,
        content_type="text/plain",
        method=AcquisitionMethod.HTTPS,
        status_code=200,
    )
    assert item.acquisition is not None
    assert item.acquisition.content_sha256 == item.content_sha256


def test_acquisition_receipt_matches_evidence() -> None:
    now = datetime(2026, 10, 6, 8, tzinfo=UTC)
    request = AcquisitionRequest(
        method=AcquisitionMethod.HTTPS,
        requested_uri="https://example.test/data",
        requested_at=now,
    )
    receipt = make_receipt(
        request,
        final_uri=request.requested_uri,
        retrieved_at=now,
        content=b"hello",
        status_code=200,
        response_media_type="text/plain",
    )
    item = EvidenceRecord.from_content(
        source=SourceRef(source_id="demo"),
        source_uri=request.requested_uri,
        content=b"hello",
        retrieved_at=now,
        content_type="text/plain",
        acquisition=receipt,
    )
    assert item.acquisition == receipt


def test_selector_range() -> None:
    selector = EvidenceSelector(
        selector_type=SelectorType.BYTE_RANGE,
        start=4,
        end=9,
        unit="bytes",
    )
    assert selector.end - selector.start == 5


def test_quality_is_explicit_not_implicitly_true() -> None:
    measured = QualityMeasurement(
        dimension=QualityDimension.COMPLETENESS,
        metric="required-field-coverage",
        value=0.8,
        method="present/expected",
        measured_at=datetime(2026, 10, 6, 8, tzinfo=UTC),
    )
    quality = DataQuality(measurements=(measured,))
    assert quality.weighted_score({QualityDimension.COMPLETENESS: 1.0}) == 0.8
    assert quality.weighted_score({QualityDimension.ACCURACY: 1.0}) is None


def test_registry_secondary_indexes() -> None:
    now = datetime(2026, 10, 6, 8, tzinfo=UTC)
    item = EvidenceRecord.from_content(
        source=SourceRef(source_id="demo"),
        source_uri="https://example.test/data",
        content=b"hello",
        retrieved_at=now,
        about_entities=(EntityRef(entity_id="entity:abc"),),
        valid_time=TimeWindow(start=now, end=now + timedelta(hours=1)),
    )
    registry = EvidenceRegistry()
    registry.add(item)
    assert registry.by_digest(item.content_sha256) == (item,)
    assert registry.by_source("demo") == (item,)
    assert registry.by_entity("entity:abc") == (item,)


def test_file_store_round_trip(tmp_path) -> None:
    store = EvidenceFileStore(tmp_path)
    digest = store.put(b"hello")
    assert store.has(digest)
    assert store.verify(digest)
    assert store.get(digest) == b"hello"
