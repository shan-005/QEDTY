from __future__ import annotations


def register_graph_routes(app, graph_provider) -> None:
    @app.get("/graph/digest")
    def graph_digest():
        return {"digest": graph_provider().digest()}
