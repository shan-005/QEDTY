from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from datetime import datetime


class QualityDimension(StrEnum):
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    AVAILABILITY = "availability"
    ACCESSIBILITY = "accessibility"
    TRACEABILITY = "traceability"
    SEMANTIC_VALIDITY = "semantic_validity"
    SPATIAL_ACCURACY = "spatial_accuracy"
    CONFORMANCE = "conformance"
    REPRESENTATION = "representation"


class QualityMeasurement(BaseModel):
    """A measurement, not an unsupported aggregate claim."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    dimension: QualityDimension
    metric: str = Field(min_length=1, max_length=256)
    value: float = Field(ge=0, le=1)
    method: str = Field(min_length=1, max_length=1024)
    measured_at: datetime
    unit: str = Field(default="ratio", min_length=1, max_length=64)
    assessor: str | None = Field(default=None, max_length=256)
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)


class DataQuality(BaseModel):
    """DQV-inspired quality profile with explicit per-dimension measurements."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    measurements: tuple[QualityMeasurement, ...] = ()
    declared_profile: str = Field(default="qedty-quality@1", min_length=1, max_length=128)

    @model_validator(mode="after")
    def unique_dimensions(self) -> Self:
        keys = [(item.dimension.value, item.metric, item.measured_at) for item in self.measurements]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate quality dimension/metric")
        return self

    def measurement(self, dimension: QualityDimension) -> tuple[QualityMeasurement, ...]:
        return tuple(item for item in self.measurements if item.dimension == dimension)

    def weighted_score(self, weights: dict[QualityDimension, float]) -> float | None:
        if not weights:
            return None
        values: list[tuple[float, float]] = []
        for dimension, weight in weights.items():
            if weight <= 0:
                raise ValueError("quality weights must be positive")
            candidates = self.measurement(dimension)
            if not candidates:
                return None
            latest = max(candidates, key=lambda item: item.measured_at)
            values.append((latest.value, weight))
        denominator = sum(weight for _, weight in values)
        return sum(value * weight for value, weight in values) / denominator
