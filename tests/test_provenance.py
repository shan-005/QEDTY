from datetime import UTC, datetime

from seraph.evidence.provenance import ProvenanceActivity


def test_provenance_create():
    p = ProvenanceActivity.create("demo", "seraph", datetime.now(UTC), "0.4.0.dev0", {"x": 1})
    assert len(p.parameters_digest) == 64
