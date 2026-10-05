from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from seraph.pci.core.enums import EpistemicStatus
from seraph.pci.core.time import ensure_utc


class ContinuityPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    timestamp: datetime
    capacity_fraction: float = Field(ge=0.0, le=1.0)
    status: EpistemicStatus = EpistemicStatus.MODELED

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ContinuityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    points: tuple[ContinuityPoint, ...]
    minimum_capacity_fraction: float = Field(ge=0.0, le=1.0)
    time_to_threshold_hours: float | None = Field(default=None, ge=0.0)
    capacity_hours: float = Field(ge=0.0)
    modeled: bool = True
