"""Immutable result models shared by graph storage and algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import TYPE_CHECKING

from qedty.core.time import ensure_utc

from .schema import KEY

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class GraphPath:
    """A deterministic simple path through the graph.

    ``score`` is the default reliability score: the product of relationship
    strength and capacity fraction along the path. ``cost`` is optional and
    is populated by cost-based path algorithms.
    """

    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    score: float
    cost: float | None = None

    def __post_init__(self) -> None:
        if len(self.entity_ids) != len(self.relationship_ids) + 1:
            raise ValueError("path requires exactly one more entity than relationship")
        if not self.entity_ids:
            raise ValueError("path cannot be empty")
        if self.score < 0 or not isfinite(self.score):
            raise ValueError("path score must be finite and non-negative")
        if self.cost is not None and (self.cost < 0 or not isfinite(self.cost)):
            raise ValueError("path cost must be finite and non-negative")

    @property
    def hops(self) -> int:
        return len(self.relationship_ids)

    @property
    def source(self) -> str:
        return self.entity_ids[0]

    @property
    def target(self) -> str:
        return self.entity_ids[-1]

    @property
    def geometric_mean_edge_score(self) -> float:
        """Return the geometric mean of the multiplicative edge score."""

        if not self.relationship_ids:
            return 1.0
        return float(self.score ** (1.0 / self.hops))

    def as_dict(self) -> dict[str, object]:
        return {
            "entity_ids": list(self.entity_ids),
            "relationship_ids": list(self.relationship_ids),
            "score": self.score,
            "cost": self.cost,
        }


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    """Read-only description of a graph at a valid-time instant."""

    at: datetime
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    schema: str = KEY

    def __post_init__(self) -> None:
        object.__setattr__(self, "at", ensure_utc(self.at))
        if self.schema != KEY:
            raise ValueError("graph snapshot schema mismatch")


@dataclass(frozen=True, slots=True)
class FlowResult:
    """Deterministic single-source/single-target flow result."""

    source: str
    target: str
    value: float
    flow_by_relationship: tuple[tuple[str, float], ...]
    source_side: tuple[str, ...] = ()
    sink_side: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphStats:
    """Structural statistics for a graph or snapshot."""

    entities: int
    relationships: int
    density: float
    self_loops: int
    isolated_entities: int
    average_in_degree: float
    average_out_degree: float
    max_in_degree: int
    max_out_degree: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "entities": self.entities,
            "relationships": self.relationships,
            "density": self.density,
            "self_loops": self.self_loops,
            "isolated_entities": self.isolated_entities,
            "average_in_degree": self.average_in_degree,
            "average_out_degree": self.average_out_degree,
            "max_in_degree": self.max_in_degree,
            "max_out_degree": self.max_out_degree,
        }
