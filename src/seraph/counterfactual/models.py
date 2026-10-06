from pydantic import BaseModel, ConfigDict, Field


class CounterfactualResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    baseline_capacity: float = Field(ge=0, le=1)
    counterfactual_capacity: float = Field(ge=0, le=1)
    continuity_gain: float
    economic_loss_delta_usd: float
    intervention_id: str
    status: str = "counterfactual"
