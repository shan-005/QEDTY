from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import EntityType, EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str = Field(min_length=1, max_length=256)
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=512)
    namespace: str = Field(default="seraph", min_length=1, max_length=128)
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("valid_from", "valid_to", "observed_at")
    @classmethod
    def utc(cls, v):
        return None if v is None else ensure_utc(v)

    @field_validator("canonical_name")
    @classmethod
    def normalize_name(cls, v):
        v = " ".join(v.split())
        if not v:
            return ValueError("canonical_name blank")
        return v

    @model_validator(mode="after")
    def valid(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude/longitude must be paired")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("invalid entity interval")
        expected = deterministic_id(
            "entity", self.namespace, self.entity_type.value, self.canonical_name.casefold()
        )
        if self.entity_id != expected:
            raise ValueError("entity_id does not match canonical identity")
        return self
