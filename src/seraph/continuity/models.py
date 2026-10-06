from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContinuityPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    timestamp: datetime
    capacity_fraction: float = Field(ge=0, le=1)


class ContinuityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    points: tuple[ContinuityPoint, ...]
    minimum_capacity_fraction: float = Field(ge=0, le=1)
    time_below_threshold_hours: float = Field(ge=0)
    capacity_hours: float = Field(ge=0)
    status: str = "modeled"
