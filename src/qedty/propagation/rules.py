"""Propagation rule configuration and edge semantics."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Any

from qedty.core.hash import sha256_hex

from .models import PropagationAggregation

if TYPE_CHECKING:
    from qedty.core.enums import RelationshipType


@dataclass(frozen=True, slots=True)
class PropagationRule:
    """Deterministic, bounded propagation policy.

    ``strength`` and ``capacity_fraction`` come from the frozen relationship
    contract.  Optional relationship attributes may refine transmission and
    latency when explicitly supplied by an upstream data model.
    """

    minimum_impairment: float = 0.01
    max_hops: int = 32
    max_signals: int = 100_000
    max_paths_per_entity: int = 64
    aggregation: PropagationAggregation = PropagationAggregation.MAX
    default_delay_seconds: float = 0.0
    max_delay_seconds: float = 365.0 * 24.0 * 3600.0
    delay_attribute_keys: tuple[str, ...] = (
        "latency_seconds",
        "delay_seconds",
        "travel_time_seconds",
    )
    transmission_attribute_key: str = "propagation_factor"
    minimum_edge_factor: float = 0.0
    allowed_relationship_types: tuple[RelationshipType, ...] | None = None
    allow_cycles: bool = False
    require_edge_active_on_arrival: bool = True
    attenuation_epsilon: float = 1e-12

    def validate(self) -> None:
        numbers = {
            "minimum_impairment": self.minimum_impairment,
            "default_delay_seconds": self.default_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "minimum_edge_factor": self.minimum_edge_factor,
            "attenuation_epsilon": self.attenuation_epsilon,
        }
        for name, value in numbers.items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 < self.minimum_impairment <= 1:
            raise ValueError("minimum_impairment must be in (0, 1]")
        if self.max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        if self.max_signals <= 0:
            raise ValueError("max_signals must be positive")
        if self.max_paths_per_entity <= 0:
            raise ValueError("max_paths_per_entity must be positive")
        if self.default_delay_seconds < 0 or self.max_delay_seconds < self.default_delay_seconds:
            raise ValueError("invalid propagation delay bounds")
        if not 0 <= self.minimum_edge_factor <= 1:
            raise ValueError("minimum_edge_factor must be in [0, 1]")
        if self.attenuation_epsilon < 0:
            raise ValueError("attenuation_epsilon must be non-negative")
        if not self.transmission_attribute_key.strip():
            raise ValueError("transmission_attribute_key must be nonblank")
        if any(not item.strip() for item in self.delay_attribute_keys):
            raise ValueError("delay attribute keys must be nonblank")

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_hex(self.to_mapping())

    def to_mapping(self) -> dict[str, Any]:
        return {
            "minimum_impairment": self.minimum_impairment,
            "max_hops": self.max_hops,
            "max_signals": self.max_signals,
            "max_paths_per_entity": self.max_paths_per_entity,
            "aggregation": self.aggregation.value,
            "default_delay_seconds": self.default_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "delay_attribute_keys": list(self.delay_attribute_keys),
            "transmission_attribute_key": self.transmission_attribute_key,
            "minimum_edge_factor": self.minimum_edge_factor,
            "allowed_relationship_types": None
            if self.allowed_relationship_types is None
            else [item.value for item in self.allowed_relationship_types],
            "allow_cycles": self.allow_cycles,
            "require_edge_active_on_arrival": self.require_edge_active_on_arrival,
            "attenuation_epsilon": self.attenuation_epsilon,
        }

    def edge_factor(self, relationship: Any) -> float:
        value = float(relationship.strength) * float(relationship.capacity_fraction)
        attributes = getattr(relationship, "attributes", None) or {}
        explicit = attributes.get(self.transmission_attribute_key)
        if explicit is not None:
            if isinstance(explicit, bool) or not isinstance(explicit, (int, float)):
                raise ValueError("relationship propagation_factor must be numeric")
            if not isfinite(float(explicit)) or not 0 <= float(explicit) <= 1:
                raise ValueError("relationship propagation_factor must be in [0, 1]")
            value *= float(explicit)
        value = max(0.0, min(1.0, value))
        return value if value >= self.minimum_edge_factor else 0.0

    def delay_seconds(self, relationship: Any) -> float:
        attributes = getattr(relationship, "attributes", None) or {}
        for key in self.delay_attribute_keys:
            value = attributes.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"relationship {key} must be numeric")
            number = float(value)
            if not isfinite(number) or not 0 <= number <= self.max_delay_seconds:
                raise ValueError(f"relationship {key} is outside allowed bounds")
            return number
        return self.default_delay_seconds

    def allows_relationship(self, relationship: Any) -> bool:
        if self.allowed_relationship_types is None:
            return True
        return relationship.relationship_type in self.allowed_relationship_types
