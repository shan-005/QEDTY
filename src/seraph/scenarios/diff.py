from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioDelta:
    changed_entities: tuple[str, ...]
    capacity_delta: dict[str, float]
    attribute_changes: dict[str, dict[str, object]]


def diff(a, b) -> ScenarioDelta:
    ids = sorted(set(a.capacities) | set(b.capacities))
    return ScenarioDelta(
        tuple(i for i in ids if a.capacities.get(i) != b.capacities.get(i)),
        {
            i: b.capacities.get(i, 0) - a.capacities.get(i, 0)
            for i in ids
            if a.capacities.get(i) != b.capacities.get(i)
        },
        {},
    )
