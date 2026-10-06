from __future__ import annotations

def register_world_routes(app, world_provider) -> None:
    @app.get("/world/summary")
    def world_summary():
        return world_provider().summary()
