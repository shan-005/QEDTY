from __future__ import annotations

def register_scenario_routes(app, scenario_provider) -> None:
    @app.get("/scenarios")
    def scenarios():
        return scenario_provider()
