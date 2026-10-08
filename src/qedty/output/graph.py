from typing import Any

from qedty.graph.store import TemporalGraph


def graph_dict(graph: TemporalGraph) -> dict[str, Any]:
    return {
        "schema": "qedty-world-graph@1.0.0",
        "digest": graph.digest(),
        "entities": [e.model_dump(mode="json") for e in graph.entities()],
        "relationships": [r.model_dump(mode="json") for r in graph.relationships()],
    }
