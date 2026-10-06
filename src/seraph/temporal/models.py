from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from seraph.core.time import ensure_utc


class Interval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid(self):
        object.__setattr__(self, "start", ensure_utc(self.start))
        object.__setattr__(self, "end", ensure_utc(self.end))
        if self.end <= self.start:
            raise ValueError("invalid interval")
        return self

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()
