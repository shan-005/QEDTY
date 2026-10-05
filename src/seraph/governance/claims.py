from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from seraph.core.enums import EpistemicStatus


class ClaimScope(StrEnum):
    OBSERVED = "observed"
    MODELED = "modeled"
    COUNTERFACTUAL = "counterfactual"


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    claim_id: str = Field(min_length=1, max_length=256)
    statement: str = Field(min_length=1, max_length=4000)
    scope: ClaimScope
    epistemic_status: EpistemicStatus
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
