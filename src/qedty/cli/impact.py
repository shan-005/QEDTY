from __future__ import annotations

from qedty.cli.scenario import demo_payload as scenario_demo


def demo_payload() -> dict[str, object]:
    payload = scenario_demo()
    return {
        "impact_status": "modeled",
        "service_capacity_fraction": payload["baseline_capacity"],
        "counterfactual_gain": payload["continuity_gain"],
        "evidence_boundary": "demo-only",
    }
