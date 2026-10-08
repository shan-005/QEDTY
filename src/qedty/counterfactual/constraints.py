from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qedty.scenarios.models import Intervention


def validate_intervention(intervention: Intervention) -> None:
    if intervention.cost_usd < 0:
        raise ValueError("negative intervention cost")
    if not intervention.protected_entity_ids and (
        intervention.transmission_reduction or intervention.capacity_gain
    ):
        raise ValueError("intervention has effects but no protected entities")
    if len(set(intervention.protected_entity_ids)) != len(intervention.protected_entity_ids):
        raise ValueError("duplicate protected entity")


def validate_budget(interventions: tuple[Intervention, ...], budget_usd: float) -> None:
    if budget_usd < 0:
        raise ValueError("budget must be non-negative")
    for i in interventions:
        validate_intervention(i)
    total = sum(i.cost_usd for i in interventions)
    if total > budget_usd:
        raise ValueError("intervention set exceeds budget")
