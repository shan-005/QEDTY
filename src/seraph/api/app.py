from __future__ import annotations

try:
    from fastapi import FastAPI
except ImportError:
    FastAPI = None

from seraph.core.version import PRODUCT_VERSION
from seraph.ontology.world import WorldModel
from seraph.graph.store import TemporalGraph

def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI extra is required: pip install seraph-pci-x[api]")
    app = FastAPI(title="SERAPH-PCI-X", version=PRODUCT_VERSION)
    world = WorldModel()
    graph = TemporalGraph()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": PRODUCT_VERSION}

    from .routes_world import register_world_routes
    from .routes_graph import register_graph_routes
    from .routes_scenarios import register_scenario_routes
    from .routes_features import register_feature_routes

    register_world_routes(app, lambda: world)
    register_graph_routes(app, lambda: graph)
    register_scenario_routes(app, lambda: [])
    register_feature_routes(app, lambda: {"type": "FeatureCollection", "features": []})
    return app
