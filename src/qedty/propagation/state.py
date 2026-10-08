"""Propagation-local derived state helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PropagationAggregation, PropagationEvent


@dataclass(frozen=True, slots=True)
class EntityPropagationState:
    """Immutable descriptive aggregate for one propagated entity."""

    entity_id: str
    impairment: float
    strongest_contribution: float
    aggregation: PropagationAggregation
    event: PropagationEvent


def aggregate_impairments(
    contributions: tuple[float, ...], aggregation: PropagationAggregation
) -> float:
    values = tuple(max(0.0, min(1.0, float(value))) for value in contributions)
    if not values:
        return 0.0
    if aggregation is PropagationAggregation.MAX:
        return max(values)
    if aggregation is PropagationAggregation.SUM_CAP:
        return min(1.0, sum(values))
    residual = 1.0
    for value in values:
        residual *= 1.0 - value
    return 1.0 - residual
