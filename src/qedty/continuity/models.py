from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qedty.core.hash import sha256_hex
from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime


class ContinuityPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    timestamp: datetime
    capacity_fraction: float = Field(ge=0, le=1)
    phase: str = "response"
    note: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> Self:
        object.__setattr__(self, "timestamp", ensure_utc(self.timestamp))
        if not self.phase.strip():
            raise ValueError("phase must not be blank")
        return self


class ContinuityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str
    points: tuple[ContinuityPoint, ...]
    minimum_capacity_fraction: float = Field(ge=0, le=1)
    time_below_threshold_hours: float = Field(ge=0)
    capacity_hours: float = Field(ge=0)
    status: str = "modeled"
    threshold: float = Field(default=0.30, ge=0, le=1)
    baseline_capacity_fraction: float = Field(default=1.0, ge=0, le=1)
    deficit_hours: float = Field(default=0, ge=0)
    resilience_index: float = Field(default=1.0, ge=0, le=1)
    time_to_threshold_hours: float | None = Field(default=None, ge=0)
    time_to_full_recovery_hours: float | None = Field(default=None, ge=0)
    fully_recovered: bool = False
    shock_ids: tuple[str, ...] = ()
    methodology: str = "piecewise-linear service trajectory"

    @model_validator(mode="after")
    def validate_trajectory(self) -> Self:
        if not self.points:
            raise ValueError("continuity result requires at least one point")
        ordered = tuple(sorted(self.points, key=lambda p: p.timestamp))
        if ordered != self.points:
            raise ValueError("continuity points must be ordered")
        if len(ordered) > 1 and any(
            a.timestamp == b.timestamp and a.capacity_fraction != b.capacity_fraction
            for a, b in itertools.pairwise(ordered)
        ):
            raise ValueError("duplicate timestamp with conflicting capacity")
        return self

    @property
    def digest(self) -> str:
        return sha256_hex(self.model_dump(mode="json"))
