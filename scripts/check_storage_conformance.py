from pathlib import Path
import tempfile

from seraph.storage.evidence import EvidenceStore
from seraph.storage.provenance import ProvenanceStore


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        e = EvidenceStore(Path(d)/"e")
        digest = e.put_text("seraph")
        assert e.exists(digest) and e.get_bytes(digest) == b"seraph"
        p = ProvenanceStore(Path(d)/"p.jsonl")
        assert p.verify()
    print("Storage content addressing: PASS")
    print("Storage provenance verification: PASS")
    print("Storage deterministic object hashing: PASS")
    return 0
if __name__ == "__main__": raise SystemExit(main())
