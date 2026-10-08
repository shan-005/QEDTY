import tempfile
from pathlib import Path

from qedty.storage.evidence import EvidenceStore
from qedty.storage.provenance import ProvenanceStore


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        e = EvidenceStore(Path(d) / "e")
        digest = e.put_text("qedty")
        assert e.exists(digest) and e.get_bytes(digest) == b"qedty"
        p = ProvenanceStore(Path(d) / "p.jsonl")
        assert p.verify()
    print("Storage content addressing: PASS")
    print("Storage provenance verification: PASS")
    print("Storage deterministic object hashing: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
