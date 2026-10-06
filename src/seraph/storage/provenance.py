from __future__ import annotations

import json
from pathlib import Path

from seraph.evidence.provenance import ProvenanceActivity


class ProvenanceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, p: ProvenanceActivity) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(p.model_dump(mode="json"), sort_keys=True) + "\n")
