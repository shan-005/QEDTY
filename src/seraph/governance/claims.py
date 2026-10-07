from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seraph.core.enums import EpistemicStatus


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    claim_id: str = Field(min_length=1, max_length=256)
    statement: str = Field(min_length=1, max_length=4000)
    status: EpistemicStatus
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    owner: str = "seraph"

    @model_validator(mode="after")
    def enforce_epistemic_controls(self) -> Claim:
        if self.status == EpistemicStatus.OBSERVED and not self.evidence_ids:
            raise ValueError("observed claim requires evidence")
        if (
            self.status in {EpistemicStatus.MODELED, EpistemicStatus.COUNTERFACTUAL}
            and not self.provenance_ids
        ):
            raise ValueError("modeled/counterfactual claim requires provenance")
        return self


def validate_claim(claim: Claim) -> Claim:
    # Pydantic validation happens at construction; this function provides an explicit control point.
    return Claim.model_validate(claim.model_dump())
