from .models import Intervention


def intervention_map(intervention: Intervention) -> dict[str, dict[str, float]]:
    return {
        eid: {
            "transmission_reduction": intervention.transmission_reduction,
            "capacity_gain": intervention.capacity_gain,
        }
        for eid in intervention.protected_entity_ids
    }
