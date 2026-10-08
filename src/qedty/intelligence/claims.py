from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qedty.core.enums import EpistemicStatus
from qedty.core.hash import sha256_hex

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class IntelligenceClaim:
    claim_id: str
    statement: str
    status: EpistemicStatus
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    confidence: float = 1.0
    provenance_ids: tuple[str, ...] = ()
    assessed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("claim_id and statement must not be blank")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")
        if self.status == EpistemicStatus.OBSERVED and not self.evidence_ids:
            raise ValueError("observed intelligence claim requires evidence")
        if (
            self.status in {EpistemicStatus.MODELED, EpistemicStatus.COUNTERFACTUAL}
            and not self.provenance_ids
        ):
            raise ValueError("modeled/counterfactual intelligence claim requires provenance")

    @property
    def digest(self) -> str:
        return sha256_hex(self)
