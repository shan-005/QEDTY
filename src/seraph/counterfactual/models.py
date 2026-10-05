from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from seraph.core.enums import InterventionType


class Intervention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    intervention_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    intervention_type: InterventionType
    cost_usd: float = Field(ge=0.0)
    protected_entities: tuple[str, ...] = ()
    transmission_reduction: float = Field(default=0.0, ge=0.0, le=1.0)
    capacity_gain: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, object] = Field(default_factory=dict)


class CounterfactualResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    baseline_minimum_capacity: float = Field(ge=0.0, le=1.0)
    counterfactual_minimum_capacity: float = Field(ge=0.0, le=1.0)
    continuity_gain: float
    intervention_id: str
    status: str = "counterfactual"
