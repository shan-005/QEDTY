from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import EntityType, EpistemicStatus
from seraph.core.ids import canonicalize_text, deterministic_id
from seraph.core.time import ensure_utc


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str = Field(min_length=1, max_length=256)
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=512)
    namespace: str = Field(default="seraph", min_length=1, max_length=128)
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = Field(default_factory=dict)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("valid_from", "valid_to", "observed_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @field_validator("canonical_name")
    @classmethod
    def _name_trimmed(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("canonical_name must not be blank")
        return normalized

    @model_validator(mode="after")
    def _valid(self) -> "Entity":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        expected = deterministic_id("entity", self.namespace, self.entity_type.value, canonicalize_text(self.canonical_name))
        if self.entity_id != expected:
            raise ValueError("entity_id does not match deterministic entity identity")
        return self
