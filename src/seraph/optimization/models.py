from __future__ import annotations
from pydantic import BaseModel,ConfigDict,Field
class RankedIntervention(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    intervention_id:str; continuity_gain:float; cost_usd:float; efficiency:float; robust_score:float
class OptimizationResult(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    recommendations:tuple[RankedIntervention,...]; objective:str; budget_usd:float
