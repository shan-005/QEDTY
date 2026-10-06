from __future__ import annotations
from pathlib import Path
from seraph.graph.persistence import save
class SnapshotStore:
    def save_graph(self,graph,path:str|Path)->None:save(graph,path)
