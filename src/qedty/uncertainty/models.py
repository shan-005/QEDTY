from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Interval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    lower: float
    estimate: float
    upper: float
    confidence_level: float = Field(default=0.9, gt=0, lt=1)
    method: str = "scenario-envelope"

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.lower <= self.estimate <= self.upper:
            raise ValueError("lower <= estimate <= upper required")
        return self

    @property
    def width(self) -> float:
        return self.upper - self.lower


class DistributionSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    name: str
    parameters: tuple[float, ...]
    seed: int = 0


class SampleSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    mean: float
    std: float
    lower: float
    median: float
    upper: float
    quantile_level: float = Field(gt=0, lt=1)
    method: str
    n: int = Field(gt=0)
