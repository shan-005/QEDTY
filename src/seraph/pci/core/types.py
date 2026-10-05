from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.pci.core.enums import EpistemicStatus, RelationshipType
from seraph.pci.core.ids import deterministic_id
from seraph.pci.core.time import ensure_utc


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str = Field(min_length=1, max_length=256)


class ScenarioRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    scenario_id: str = Field(min_length=1, max_length=256)
    parent_id: str | None = None


class ContinuityWindow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _ordered(self) -> "ContinuityWindow":
        if self.end <= self.start:
            raise ValueError("continuity window end must be after start")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    observation_id: str = Field(min_length=1, max_length=256)
    entity_id: str = Field(min_length=1, max_length=256)
    observed_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    property_name: str = Field(min_length=1, max_length=128)
    value: Any
    unit: str | None = Field(default=None, max_length=64)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: tuple[str, ...] = ()
    source_record_id: str | None = None

    @field_validator("observed_at", "valid_from", "valid_to")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def _interval(self) -> "Observation":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class Relationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    relationship_id: str = Field(min_length=1, max_length=256)
    source: EntityRef
    target: EntityRef
    relationship_type: RelationshipType
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, gt=0.0, le=1.0e9)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("valid_from", "valid_to", "observed_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def _validate_interval_and_self_loop(self) -> "Relationship":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.source.entity_id == self.target.entity_id and self.relationship_type != RelationshipType.MEMBER_OF:
            raise ValueError("self-loop is not allowed for this relationship type")
        expected = deterministic_id(
            "rel",
            self.source.entity_id,
            self.target.entity_id,
            self.relationship_type.value,
            self.valid_from.isoformat() if self.valid_from else None,
            self.valid_to.isoformat() if self.valid_to else None,
        )
        if self.relationship_id != expected:
            raise ValueError("relationship_id does not match deterministic relationship identity")
        return self


class PathResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    hops: int = Field(ge=0)
    confidence_product: float = Field(ge=0.0, le=1.0)

    @classmethod
    def from_path(cls, entity_ids: list[str], relationship_ids: list[str], confidence_product: float) -> "PathResult":
        return cls(entity_ids=tuple(entity_ids), relationship_ids=tuple(relationship_ids), hops=len(relationship_ids), confidence_product=confidence_product)
