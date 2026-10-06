from __future__ import annotations

from dataclasses import dataclass

from seraph.core.enums import EpistemicStatus


@dataclass(frozen=True)
class IntelligenceClaim:
    claim_id: str
    statement: str
    status: EpistemicStatus
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]
