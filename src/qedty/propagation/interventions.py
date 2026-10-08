"""Propagation-facing intervention utilities with legacy compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def merge_attenuation_maps(
    *maps: dict[str, float] | None,
) -> dict[str, float]:
    """Merge attenuation maps conservatively by maximum reduction."""
    result: dict[str, float] = {}
    for mapping in maps:
        if not mapping:
            continue
        for entity_id, value in mapping.items():
            number = float(value)
            if not 0 <= number <= 1:
                raise ValueError("transmission reductions must be in [0, 1]")
            result[entity_id] = max(result.get(entity_id, 0.0), number)
    return dict(sorted(result.items()))


def merge_capacity_gains(*maps: dict[str, float] | None) -> dict[str, float]:
    """Merge gains by maximum to avoid silently multiplying interventions."""
    result: dict[str, float] = {}
    for mapping in maps:
        if not mapping:
            continue
        for entity_id, value in mapping.items():
            number = float(value)
            if not 0 <= number <= 1:
                raise ValueError("capacity gains must be in [0, 1]")
            result[entity_id] = max(result.get(entity_id, 0.0), number)
    return dict(sorted(result.items()))


def attenuation_for(
    entity_id: str,
    transmission_reductions: dict[str, float],
    capacity_gains: dict[str, float],
) -> float:
    reduction = transmission_reductions.get(entity_id, 0.0)
    gain = capacity_gains.get(entity_id, 0.0)
    return max(0.0, min(1.0, (1.0 - reduction) * (1.0 - gain)))


def active_intervention_effects(
    interventions: tuple[object, ...],
    at: datetime | None,
) -> tuple[dict[str, float], dict[str, float]]:
    reductions: dict[str, float] = {}
    gains: dict[str, float] = {}
    for intervention in interventions:
        active_at = getattr(intervention, "active_at", None)
        if callable(active_at) and not active_at(at):
            continue
        protected = tuple(getattr(intervention, "protected_entity_ids", ()))
        reduction = float(getattr(intervention, "transmission_reduction", 0.0))
        gain = float(getattr(intervention, "capacity_gain", 0.0))
        for entity_id in protected:
            reductions[entity_id] = max(reductions.get(entity_id, 0.0), reduction)
            gains[entity_id] = max(gains.get(entity_id, 0.0), gain)
    return dict(sorted(reductions.items())), dict(sorted(gains.items()))
