from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from seraph.core.hash import sha256_hex


class CounterfactualResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    baseline_capacity: float = Field(ge=0, le=1)
    counterfactual_capacity: float = Field(ge=0, le=1)
    continuity_gain: float
    economic_loss_delta_usd: float
    intervention_id: str
    status: str = "counterfactual"
    baseline_digest: str | None = None
    counterfactual_digest: str | None = None
    assumptions: tuple[str, ...] = ()
    methodology: str = "propagation+continuity intervention comparison"

    @property
    def digest(self) -> str:
        return sha256_hex(self.model_dump(mode="json"))
