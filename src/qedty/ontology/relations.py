from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.enums import EpistemicStatus, RelationshipType
from qedty.core.hash import deterministic_id
from qedty.core.time import ensure_utc
from qedty.core.units import TIME, Quantity

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.types import EntityRef, TimeWindow


class Relationship(BaseModel):
    """Typed, directed and temporally valid edge in the QEDTY world model."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    relationship_id: str = Field(min_length=1, max_length=256)
    source: EntityRef
    target: EntityRef
    relationship_type: RelationshipType
    valid_time: TimeWindow | None = None
    observed_at: datetime | None = None
    strength: float = Field(default=1.0, ge=0, le=1)
    capacity_fraction: float = Field(default=1.0, ge=0, le=1)
    reliability: float = Field(default=1.0, ge=0, le=1)
    latency: Quantity | None = None
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def observed_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.source.entity_id == self.target.entity_id
            and self.relationship_type != RelationshipType.MEMBER_OF
        ):
            raise ValueError("self relationship prohibited except member_of")
        if self.latency is not None:
            if self.latency.dimension != TIME:
                raise ValueError("latency must have time dimension")
            if self.latency.value < 0:
                raise ValueError("latency must be non-negative")
        expected = deterministic_id(
            "rel",
            self.source.entity_id,
            self.target.entity_id,
            self.relationship_type.value,
            self.valid_time.start.isoformat() if self.valid_time else None,
            self.valid_time.end.isoformat() if self.valid_time else None,
        )
        if self.relationship_id != expected:
            raise ValueError("relationship_id mismatch")
        return self

    @property
    def valid_from(self) -> datetime | None:
        return None if self.valid_time is None else self.valid_time.start

    @property
    def valid_to(self) -> datetime | None:
        return None if self.valid_time is None else self.valid_time.end

    @property
    def is_operational(self) -> bool:
        return self.capacity_fraction > 0 and self.reliability > 0

    def effective_strength(self) -> float:
        return self.strength * self.capacity_fraction * self.reliability
