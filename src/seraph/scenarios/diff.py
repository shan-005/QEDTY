"""Deterministic scenario and materialized-state diffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Scenario
    from .state import ScenarioState


@dataclass(frozen=True, slots=True)
class ScenarioDelta:
    changed_entities: tuple[str, ...]
    capacity_delta: dict[str, float]
    attribute_changes: dict[str, dict[str, object]]
    added_entities: tuple[str, ...] = ()
    removed_entities: tuple[str, ...] = ()
    transmission_reduction_delta: dict[str, float] | None = None
    scenario_a_digest: str | None = None
    scenario_b_digest: str | None = None

    @property
    def changed_count(self) -> int:
        return len(self.changed_entities)


def diff(a: Scenario, b: Scenario) -> ScenarioDelta:
    ids = sorted(set(a.capacities) | set(b.capacities))
    changed = tuple(
        entity_id for entity_id in ids if a.capacities.get(entity_id) != b.capacities.get(entity_id)
    )
    capacity_delta = {
        entity_id: b.capacities.get(entity_id, 0.0) - a.capacities.get(entity_id, 0.0)
        for entity_id in changed
    }
    return ScenarioDelta(
        changed_entities=changed,
        capacity_delta=capacity_delta,
        attribute_changes={},
        scenario_a_digest=a.digest,
        scenario_b_digest=b.digest,
    )


def state_diff(a: ScenarioState, b: ScenarioState) -> ScenarioDelta:
    ids = sorted(set(a.capacities) | set(b.capacities) | set(a.attributes) | set(b.attributes))
    changed = tuple(
        entity_id
        for entity_id in ids
        if a.capacities.get(entity_id) != b.capacities.get(entity_id)
        or a.attributes.get(entity_id, {}) != b.attributes.get(entity_id, {})
    )
    capacity_delta = {
        entity_id: b.capacities.get(entity_id, 0.0) - a.capacities.get(entity_id, 0.0)
        for entity_id in changed
        if a.capacities.get(entity_id) != b.capacities.get(entity_id)
    }
    attribute_changes = {
        entity_id: _attribute_delta(
            a.attributes.get(entity_id, {}), b.attributes.get(entity_id, {})
        )
        for entity_id in changed
        if a.attributes.get(entity_id, {}) != b.attributes.get(entity_id, {})
    }
    transmission_ids = sorted(set(a.transmission_reductions) | set(b.transmission_reductions))
    transmission_delta = {
        entity_id: b.transmission_reductions.get(entity_id, 0.0)
        - a.transmission_reductions.get(entity_id, 0.0)
        for entity_id in transmission_ids
        if a.transmission_reductions.get(entity_id) != b.transmission_reductions.get(entity_id)
    }
    return ScenarioDelta(
        changed_entities=changed,
        capacity_delta=capacity_delta,
        attribute_changes=attribute_changes,
        added_entities=tuple(sorted(set(b.capacities) - set(a.capacities))),
        removed_entities=tuple(sorted(set(a.capacities) - set(b.capacities))),
        transmission_reduction_delta=transmission_delta,
        scenario_a_digest=a.digest,
        scenario_b_digest=b.digest,
    )


def _attribute_delta(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            out[key] = {"before": a.get(key), "after": b.get(key)}
    return out
