from __future__ import annotations

from seraph.cli.scenario import demo_payload as scenario_demo

def demo_payload() -> dict[str, object]:
    payload = scenario_demo()
    return {
        "optimization_status": "modeled",
        "recommended_intervention": "demo-backup",
        "continuity_gain": payload["continuity_gain"],
        "cost_usd": payload["intervention_cost_usd"],
    }
