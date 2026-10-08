from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.enums import EpistemicStatus
from qedty.core.hash import deterministic_id
from qedty.core.time import ensure_utc

from .schema import normalize_text

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.types import EntityRef, TimeWindow
    from qedty.core.units import Quantity

    from .terms import CapabilityKind


class Capability(BaseModel):
    """Quantified capacity exposed by an entity, with validity and provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    capability_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    kind: CapabilityKind
    nominal_capacity: Quantity
    minimum_capacity: Quantity | None = None
    maximum_capacity: Quantity | None = None
    owner: EntityRef
    availability_fraction: float = Field(default=1.0, ge=0, le=1)
    valid_time: TimeWindow | None = None
    observed_at: datetime | None = None
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=256)

    @field_validator("observed_at")
    @classmethod
    def observed_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def validate_capacity(self) -> Self:
        if self.nominal_capacity.value < 0:
            raise ValueError("nominal_capacity must be non-negative")
        if self.nominal_capacity.definition.is_affine:
            raise ValueError("nominal_capacity must use a non-affine unit")
        for label, quantity in (
            ("minimum_capacity", self.minimum_capacity),
            ("maximum_capacity", self.maximum_capacity),
        ):
            if quantity is not None:
                if quantity.definition.is_affine:
                    raise ValueError(f"{label} must use a non-affine unit")
                if quantity.dimension != self.nominal_capacity.dimension:
                    raise ValueError(f"{label} dimension must match nominal_capacity")
        if (
            self.minimum_capacity
            and self.nominal_capacity.si_value < self.minimum_capacity.si_value
        ):
            raise ValueError("nominal_capacity must be >= minimum_capacity")
        if (
            self.maximum_capacity
            and self.nominal_capacity.si_value > self.maximum_capacity.si_value
        ):
            raise ValueError("nominal_capacity must be <= maximum_capacity")
        expected = deterministic_id(
            "capability",
            self.owner.entity_id,
            self.kind.value,
            self.name.casefold(),
        )
        if self.capability_id != expected:
            raise ValueError("capability_id mismatch")
        return self

    @property
    def owner_entity_id(self) -> str:
        return self.owner.entity_id

    def effective_capacity(self) -> Quantity:
        return self.nominal_capacity.scaled(self.availability_fraction)
