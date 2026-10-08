from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RankedIntervention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    intervention_id: str
    continuity_gain: float
    cost_usd: float
    efficiency: float
    robust_score: float
    risk_score: float = 0.0
    selected: bool = False
    rationale: str = ""

    @property
    def gain_per_dollar(self) -> float:
        return self.efficiency / 1_000_000 if self.cost_usd else self.continuity_gain


class OptimizationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    recommendations: tuple[RankedIntervention, ...]
    objective: str
    budget_usd: float
    selected_intervention_ids: tuple[str, ...] = ()
    spent_usd: float = 0.0
    robust_floor: float = 0.0
    status: str = "optimal_reference"
    digest: str = Field(default="", min_length=0)
