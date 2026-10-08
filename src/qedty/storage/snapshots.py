from __future__ import annotations

import gzip
import json
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qedty.graph.persistence import load, save

if TYPE_CHECKING:
    from qedty.graph.store import TemporalGraph


class SnapshotStore:
    """Deterministic graph snapshot store with optional compressed JSON envelope."""

    def save_graph(self, graph: TemporalGraph, path: str | Path) -> None:
        save(graph, path)

    def save_json(self, payload: Any, path: str | Path, *, compress: bool = True) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        target = p.with_suffix(p.suffix + ".gz") if compress else p
        if compress:
            target.write_bytes(gzip.compress(encoded, mtime=0))
        else:
            target.write_bytes(encoded)
        return sha256(encoded).hexdigest()

    def load_graph(self, path: str | Path) -> TemporalGraph:
        return load(path)
