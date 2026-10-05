from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.pci.core.enums import EpistemicStatus
from seraph.pci.core.time import ensure_utc


class GNSSDependency(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    source_entity_id: str
    target_entity_id: str
    dependency_fraction: float = Field(ge=0.0, le=1.0)
    transmission_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    status: EpistemicStatus = EpistemicStatus.MODELED


class GNSSScenario(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    name: str
    start: datetime
    end: datetime
    source_entity_id: str
    availability_fraction: float = Field(ge=0.0, le=1.0)
    geography_entity_id: str | None = None
    notes: str = ""

    @field_validator("start", "end")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _ordered(self) -> "GNSSScenario":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
