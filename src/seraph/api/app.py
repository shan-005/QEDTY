from __future__ import annotations

from typing import TYPE_CHECKING, Any

from seraph.core.version import PRODUCT_VERSION
from seraph.graph.store import TemporalGraph
from seraph.ontology.world import WorldModel

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_app() -> FastAPI:
    try:
        from fastapi import FastAPI as FastAPIClass
    except ImportError as exc:
        raise RuntimeError("FastAPI extra is required: uv pip install -e '.[api]'") from exc
    app: FastAPI = FastAPIClass(
        title="SERAPH-PCI-X",
        version=PRODUCT_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    world = WorldModel()
    graph = TemporalGraph()

    from .routes_features import register_feature_routes
    from .routes_graph import register_graph_routes
    from .routes_scenarios import register_scenario_routes
    from .routes_world import register_world_routes

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": PRODUCT_VERSION}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready", "version": PRODUCT_VERSION}

    @app.get("/metadata")
    def metadata() -> dict[str, Any]:
        return {
            "product": "SERAPH-PCI-X",
            "version": PRODUCT_VERSION,
            "api_version": "1.0.0",
            "contract": "OpenAPI 3.1.1",
        }

    register_world_routes(app, lambda: world)
    register_graph_routes(app, lambda: graph)
    register_scenario_routes(app, list)
    register_feature_routes(app, lambda: {"type": "FeatureCollection", "features": []})
    return app
