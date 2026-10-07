from datetime import UTC, datetime

from seraph.evidence.provenance import ProvenanceActivity


def test_provenance_create():
    p = ProvenanceActivity.create(
        activity="demo",
        agent="seraph",
        started_at=datetime.now(UTC),
        parameters={"x": 1},
    )
    assert len(p.parameters_digest) == 64
