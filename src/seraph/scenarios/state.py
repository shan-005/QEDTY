"""Mutable execution state for deterministic scenario application."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from seraph.core.hash import sha256_hex
from seraph.core.time import ensure_utc

from .models import PatchOperation, StatePatch

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class ScenarioState:
    """Materialized state used by scenario/propagation engines.

    The state is deliberately independent from a persistent database.  It can
    be serialized into a canonical digest and later persisted by ``storage``.
    """

    capacities: dict[str, float] = field(default_factory=dict)
    attributes: dict[str, dict[str, object]] = field(default_factory=dict)
    transmission_reductions: dict[str, float] = field(default_factory=dict)
    active_shock_ids: tuple[str, ...] = ()
    applied_intervention_ids: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    world_digest: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.capacities = dict(sorted(self.capacities.items()))
        self.attributes = deepcopy(self.attributes)
        self.transmission_reductions = dict(sorted(self.transmission_reductions.items()))
        self.active_shock_ids = tuple(sorted(set(self.active_shock_ids)))
        self.applied_intervention_ids = tuple(sorted(set(self.applied_intervention_ids)))
        self.lineage = tuple(self.lineage)
        if self.evaluated_at is not None:
            self.evaluated_at = ensure_utc(self.evaluated_at)
        self.validate()

    def validate(self) -> None:
        for key, value in self.capacities.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"capacity {key!r} must be between 0 and 1")
        for key, value in self.transmission_reductions.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"transmission reduction {key!r} must be between 0 and 1")

    def copy(self) -> ScenarioState:
        return ScenarioState(
            capacities=self.capacities,
            attributes=self.attributes,
            transmission_reductions=self.transmission_reductions,
            active_shock_ids=self.active_shock_ids,
            applied_intervention_ids=self.applied_intervention_ids,
            lineage=self.lineage,
            world_digest=self.world_digest,
            evaluated_at=self.evaluated_at,
        )

    @property
    def digest(self) -> str:
        return sha256_hex(self.to_mapping())

    def to_mapping(self) -> dict[str, Any]:
        return {
            "capacities": dict(sorted(self.capacities.items())),
            "attributes": self._canonical_attributes(self.attributes),
            "transmission_reductions": dict(sorted(self.transmission_reductions.items())),
            "active_shock_ids": sorted(self.active_shock_ids),
            "applied_intervention_ids": sorted(self.applied_intervention_ids),
            "lineage": list(self.lineage),
            "world_digest": self.world_digest,
            "evaluated_at": self.evaluated_at.isoformat().replace("+00:00", "Z")
            if self.evaluated_at is not None
            else None,
        }

    @staticmethod
    def _canonical_attributes(value: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        return {
            entity_id: {key: value[entity_id][key] for key in sorted(value[entity_id])}
            for entity_id in sorted(value)
        }

    def capacity(self, entity_id: str, default: float = 1.0) -> float:
        return self.capacities.get(entity_id, default)

    def set_capacity(self, entity_id: str, value: float) -> None:
        self.capacities[entity_id] = max(0.0, min(1.0, float(value)))

    def apply_patch(self, patch: StatePatch) -> None:
        if patch.path == "capacity":
            self._apply_capacity_patch(patch)
            return
        self._apply_attribute_patch(patch)

    def apply_patches(self, patches: tuple[StatePatch, ...] | list[StatePatch]) -> None:
        for patch in patches:
            self.apply_patch(patch)
        self.validate()

    def _apply_capacity_patch(self, patch: StatePatch) -> None:
        if patch.operation is PatchOperation.REMOVE:
            self.capacities.pop(patch.entity_id, None)
            return
        if not isinstance(patch.value, (int, float)) or isinstance(patch.value, bool):
            raise ValueError("capacity patches require a numeric value")
        current = self.capacities.get(patch.entity_id, 1.0)
        value = float(patch.value)
        if patch.operation is PatchOperation.SET:
            result = value
        elif patch.operation is PatchOperation.ADD:
            result = current + value
        elif patch.operation is PatchOperation.MULTIPLY:
            result = current * value
        elif patch.operation is PatchOperation.MIN:
            result = min(current, value)
        elif patch.operation is PatchOperation.MAX:
            result = max(current, value)
        else:  # pragma: no cover
            raise ValueError(f"unsupported patch operation: {patch.operation}")
        self.set_capacity(patch.entity_id, result)

    def _apply_attribute_patch(self, patch: StatePatch) -> None:
        path = patch.path.removeprefix("attributes.").split(".")
        current = self.attributes.setdefault(patch.entity_id, {})
        if patch.operation is PatchOperation.REMOVE:
            self._delete_nested(current, path)
            return
        existing = self._get_nested(current, path)
        if patch.operation is PatchOperation.SET or existing is None:
            value: object = deepcopy(patch.value)
        else:
            value = self._combine(existing, patch.value, patch.operation)
        self._set_nested(current, path, value)

    @staticmethod
    def _combine(existing: object, value: object, operation: PatchOperation) -> object:
        if not isinstance(existing, (int, float)) or isinstance(existing, bool):
            raise ValueError("numeric attribute operations require numeric existing value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("numeric attribute operations require numeric patch value")
        if operation is PatchOperation.ADD:
            return existing + value
        if operation is PatchOperation.MULTIPLY:
            return existing * value
        if operation is PatchOperation.MIN:
            return min(existing, value)
        if operation is PatchOperation.MAX:
            return max(existing, value)
        raise ValueError(f"unsupported attribute operation: {operation}")

    @staticmethod
    def _get_nested(mapping: dict[str, object], path: list[str]) -> object | None:
        current: object = mapping
        for part in path:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _set_nested(mapping: dict[str, object], path: list[str], value: object) -> None:
        current = mapping
        for part in path[:-1]:
            child = current.get(part)
            if not isinstance(child, dict):
                child = {}
                current[part] = child
            current = child
        current[path[-1]] = value

    @staticmethod
    def _delete_nested(mapping: dict[str, object], path: list[str]) -> None:
        current: object = mapping
        for part in path[:-1]:
            if not isinstance(current, dict) or part not in current:
                return
            current = current[part]
        if isinstance(current, dict):
            current.pop(path[-1], None)

    def with_evaluation(self, at: datetime | None) -> None:
        self.evaluated_at = None if at is None else ensure_utc(at)
