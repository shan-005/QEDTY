from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from seraph.graph.store import TemporalGraph


def register_graph_routes(app: FastAPI, graph_provider: Callable[[], TemporalGraph]) -> None:
    @app.get("/graph/digest")
    def graph_digest() -> dict[str, str]:
        return {"digest": graph_provider().digest()}
