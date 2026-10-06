from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


from seraph.core.version import PRODUCT_VERSION
from seraph.graph.store import TemporalGraph
from seraph.ontology.world import WorldModel


def create_app() -> FastAPI:
    try:
        from fastapi import FastAPI as FastAPIClass
    except ImportError as exc:
        raise RuntimeError("FastAPI extra is required: pip install seraph-pci-x[api]") from exc
    app: FastAPI = FastAPIClass(title="SERAPH-PCI-X", version=PRODUCT_VERSION)
    world = WorldModel()
    graph = TemporalGraph()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": PRODUCT_VERSION}

    from .routes_features import register_feature_routes
    from .routes_graph import register_graph_routes
    from .routes_scenarios import register_scenario_routes
    from .routes_world import register_world_routes

    register_world_routes(app, lambda: world)
    register_graph_routes(app, lambda: graph)
    register_scenario_routes(app, list)
    register_feature_routes(app, lambda: {"type": "FeatureCollection", "features": []})
    return app
