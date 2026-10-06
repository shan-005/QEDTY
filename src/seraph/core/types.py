from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import EpistemicStatus
from .hash import deterministic_id
from .time import ensure_utc


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str = Field(min_length=1, max_length=256)


class TimeWindow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def ordered(self) -> TimeWindow:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class AssertionRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    assertion_id: str = Field(min_length=1, max_length=256)
    status: EpistemicStatus


class DeterministicKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    namespace: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=256)

    @property
    def id(self) -> str:
        return deterministic_id(self.namespace, self.value)
