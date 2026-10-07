"""Intervention semantics for scenario execution and counterfactual reuse."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from .models import Intervention


def intervention_map(intervention: Intervention) -> dict[str, dict[str, float]]:
    """Backward-compatible mapping used by the counterfactual engine."""
    return {
        entity_id: {
            "transmission_reduction": intervention.transmission_reduction,
            "capacity_gain": intervention.capacity_gain,
        }
        for entity_id in intervention.protected_entity_ids
    }


def active_interventions(
    interventions: tuple[Intervention, ...], at: datetime | None
) -> tuple[Intervention, ...]:
    return tuple(
        sorted(
            (item for item in interventions if item.active_at(at)),
            key=lambda x: x.intervention_id,
        )
    )


def transmission_reduction_for(intervention: Intervention, entity_id: str) -> float:
    if entity_id not in intervention.protected_entity_ids:
        return 0.0
    return intervention.transmission_reduction


def capacity_gain_for(intervention: Intervention, entity_id: str) -> float:
    if entity_id not in intervention.protected_entity_ids:
        return 0.0
    return intervention.capacity_gain
