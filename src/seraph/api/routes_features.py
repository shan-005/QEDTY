from __future__ import annotations

def register_feature_routes(app, feature_provider) -> None:
    @app.get("/collections/world/features")
    def world_features():
        return feature_provider()
