from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.enums import EpistemicStatus
from qedty.core.hash import deterministic_id
from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.types import EntityRef, TimeWindow
    from qedty.core.units import Quantity

    from .terms import FlowKind


class Flow(BaseModel):
    """Directional transfer of a typed quantity between entities over time."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    flow_id: str = Field(min_length=1, max_length=256)
    flow_type: FlowKind
    source: EntityRef
    target: EntityRef
    quantity: Quantity
    valid_time: TimeWindow
    observed_at: datetime | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def observed_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def identity(self) -> Self:
        if self.quantity.value < 0:
            raise ValueError("flow quantity must be non-negative")
        if self.quantity.definition.is_affine:
            raise ValueError("flow quantity must use a non-affine unit")
        if self.source.entity_id == self.target.entity_id:
            raise ValueError("flow source and target must differ")
        quantity_token = format(self.quantity.value.normalize(), "f")
        expected = deterministic_id(
            "flow",
            self.flow_type.value,
            self.source.entity_id,
            self.target.entity_id,
            quantity_token,
            self.quantity.unit,
            self.valid_time.start.isoformat(),
            self.valid_time.end.isoformat(),
        )
        if self.flow_id != expected:
            raise ValueError("flow_id mismatch")
        return self

    @property
    def source_entity_id(self) -> str:
        return self.source.entity_id

    @property
    def target_entity_id(self) -> str:
        return self.target.entity_id

    @property
    def unit(self) -> str:
        return self.quantity.unit

    @property
    def period(self) -> str:
        return self.valid_time.start.isoformat() + "/" + self.valid_time.end.isoformat()
