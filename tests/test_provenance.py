from datetime import UTC, datetime

from qedty.evidence.provenance import ProvenanceActivity


def test_provenance_create():
    p = ProvenanceActivity.create(
        activity="demo",
        agent="qedty",
        started_at=datetime.now(UTC),
        parameters={"x": 1},
    )
    assert len(p.parameters_digest) == 64
