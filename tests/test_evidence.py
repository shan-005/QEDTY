import hashlib
from datetime import UTC, datetime

from seraph.core.hash import deterministic_id
from seraph.evidence.models import EvidenceRecord


def test_evidence_identity():
    b = b"hello"
    d = hashlib.sha256(b).hexdigest()
    uri = "test://1"
    x = EvidenceRecord(
        evidence_id=deterministic_id("evidence", uri, d, None),
        source_name="test",
        source_uri=uri,
        retrieved_at=datetime.now(UTC),
        content_sha256=d,
    )
    assert x.evidence_id.startswith("evidence:")
