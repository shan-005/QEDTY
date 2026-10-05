from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UncertaintyInterval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    lower: float
    estimate: float
    upper: float
    confidence_level: float = Field(default=0.90, gt=0.0, lt=1.0)
    method: str = "scenario-envelope"

    @model_validator(mode="after")
    def _ordered(self) -> "UncertaintyInterval":
        if not self.lower <= self.estimate <= self.upper:
            raise ValueError("require lower <= estimate <= upper")
        return self
