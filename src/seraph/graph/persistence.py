from __future__ import annotations

import json
from pathlib import Path

from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship

from .store import TemporalGraph


def save(graph: TemporalGraph, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(
            {
                "entities": [e.model_dump(mode="json") for e in graph.entities()],
                "relationships": [r.model_dump(mode="json") for r in graph.relationships()],
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def load(path: str | Path) -> TemporalGraph:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    g = TemporalGraph()
    for x in raw.get("entities", []):
        g.add_entity(Entity.model_validate(x, strict=False))
    for x in raw.get("relationships", []):
        g.add_relationship(Relationship.model_validate(x, strict=False))
    return g
