from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from seraph.pci.counterfactual.models import Intervention


class RankedIntervention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    intervention: Intervention
    continuity_gain: float
    gain_per_million_usd: float
    rank_score: float


class OptimizationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    recommendations: tuple[RankedIntervention, ...]
