from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import ShockType
from seraph.core.ids import deterministic_id
from seraph.core.time import ensure_utc


class Shock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    shock_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    shock_type: ShockType
    source_entity_id: str = Field(min_length=1, max_length=256)
    start: datetime
    end: datetime
    severity: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start", "end")
    @classmethod
    def _timestamps(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _valid(self) -> "Shock":
        if self.end <= self.start:
            raise ValueError("shock end must be after start")
        expected = deterministic_id(
            "shock", self.name, self.shock_type.value, self.source_entity_id,
            self.start.isoformat(), self.end.isoformat(), self.severity,
        )
        if self.shock_id != expected:
            raise ValueError("shock_id does not match deterministic shock identity")
        return self

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0
