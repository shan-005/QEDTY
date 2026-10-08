from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from qedty.core.errors import StorageError
from qedty.evidence import EvidenceFileStore, ProvenanceActivity, ProvenanceChain


def test_content_store_rejects_bad_digest(tmp_path) -> None:
    store = EvidenceFileStore(tmp_path)
    with pytest.raises(StorageError):
        store.get("0" * 64)


def test_provenance_topological_order() -> None:
    t0 = datetime(2026, 10, 6, 8, tzinfo=UTC)
    first = ProvenanceActivity.create(
        activity="acquire",
        agent="collector",
        started_at=t0,
        ended_at=t0 + timedelta(seconds=1),
        parameters={"uri": "https://example.test"},
    )
    second = ProvenanceActivity.create(
        activity="normalize",
        agent="normalizer",
        started_at=t0 + timedelta(seconds=2),
        ended_at=t0 + timedelta(seconds=3),
        parameters={"profile": "qedty-normalization@1"},
        parent_ids=(first.provenance_id,),
    )
    chain = ProvenanceChain()
    chain.add(first)
    chain.add(second)
    assert tuple(item.provenance_id for item in chain.topological()) == (
        first.provenance_id,
        second.provenance_id,
    )
    assert chain.ancestors(second.provenance_id) == (first.provenance_id,)
