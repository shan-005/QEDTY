from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seraph.evidence.provenance import ProvenanceActivity


class ProvenanceStore:
    """Append-only hash-chained provenance journal.

    Each record includes the previous record hash. Reordering or truncation is
    therefore detectable without requiring a separate database server.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last = ""
        with self.path.open("rb") as f:
            for raw in f:
                if raw.strip():
                    last = raw.decode("utf-8").rstrip("\n")
        if not last:
            return "0" * 64
        return sha256(last.encode("utf-8")).hexdigest()

    def append(self, p: ProvenanceActivity) -> str:
        payload = p.model_dump(mode="json")
        with self._lock:
            prev = self._last_hash()
            row = {"record": payload, "prev_hash": prev}
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8") as f:
                f.write(encoded + "\n")
            return sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        if not self.path.exists():
            return True
        previous = "0" * 64
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("prev_hash") != previous:
                    return False
                previous = sha256(line.rstrip("\n").encode("utf-8")).hexdigest()
        return True
