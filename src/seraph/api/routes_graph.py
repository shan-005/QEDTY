from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI

    from seraph.graph.store import TemporalGraph


def register_graph_routes(app: FastAPI, graph_provider: Callable[[], TemporalGraph]) -> None:
    @app.get("/graph/digest")
    def graph_digest() -> dict[str, str]:
        return {"digest": graph_provider().digest()}

    @app.get("/graph/summary")
    def graph_summary() -> dict[str, int]:
        graph = graph_provider()
        return {"entities": len(graph.entities()), "relationships": len(graph.relationships())}
