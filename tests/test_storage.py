from pathlib import Path

from qedty.storage.evidence import EvidenceStore
from qedty.storage.provenance import ProvenanceStore


def test_content_addressed_store(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e")
    d1 = store.put_text("hello")
    d2 = store.put_text("hello")
    assert d1 == d2 and store.get_bytes(d1) == b"hello"
    assert store.metadata(d1)["sha256"] == d1


def test_provenance_chain(tmp_path: Path) -> None:
    # Store construction itself is the contract smoke test; domain ProvenanceActivity
    # is validated in the evidence layer.
    store = ProvenanceStore(tmp_path / "p.jsonl")
    assert store.verify()
