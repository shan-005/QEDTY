from seraph.scenarios.models import Intervention


def validate_intervention(intervention: Intervention) -> None:
    if intervention.cost_usd < 0:
        raise ValueError("negative intervention cost")
    if not intervention.protected_entity_ids and (
        intervention.transmission_reduction or intervention.capacity_gain
    ):
        raise ValueError("intervention has effects but no protected entities")
