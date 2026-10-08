from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ClaimPolicy:
    allow_unknown: bool = False
    require_evidence_for_observed: bool = True
    require_provenance_for_modeled: bool = True
    minimum_confidence: float = 0.0
    require_limitations_for_counterfactual: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be in [0,1]")


def enforce(
    status: str,
    evidence_ids: tuple[str, ...],
    provenance_ids: tuple[str, ...],
    policy: ClaimPolicy,
    *,
    confidence: float = 1.0,
    limitations: tuple[str, ...] = (),
) -> None:
    if status == "unknown" and not policy.allow_unknown:
        raise ValueError("unknown claim status is not allowed")
    if status == "observed" and policy.require_evidence_for_observed and not evidence_ids:
        raise ValueError("observed claim requires evidence")
    if status == "modeled" and policy.require_provenance_for_modeled and not provenance_ids:
        raise ValueError("modeled claim requires provenance")
    if (
        status == "counterfactual"
        and policy.require_limitations_for_counterfactual
        and not limitations
    ):
        raise ValueError("counterfactual claim requires limitations")
    if not 0 <= confidence <= 1 or confidence < policy.minimum_confidence:
        raise ValueError("claim confidence below governance threshold")


def evaluate(
    status: str,
    evidence_ids: tuple[str, ...],
    provenance_ids: tuple[str, ...],
    policy: ClaimPolicy,
    *,
    confidence: float = 1.0,
    limitations: tuple[str, ...] = (),
) -> Decision:
    try:
        enforce(
            status,
            evidence_ids,
            provenance_ids,
            policy,
            confidence=confidence,
            limitations=limitations,
        )
    except ValueError:
        return Decision.DENY
    if confidence < 0.5:
        return Decision.REVIEW
    return Decision.ALLOW
