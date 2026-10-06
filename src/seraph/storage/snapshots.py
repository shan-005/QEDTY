from __future__ import annotations

from pathlib import Path

from seraph.graph.persistence import save
from seraph.graph.store import TemporalGraph


class SnapshotStore:
    def save_graph(self, graph: TemporalGraph, path: str | Path) -> None:
        save(graph, path)
