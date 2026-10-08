from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class AssuranceRecord:
    scope: str
    passed: bool
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    control_ids: tuple[str, ...] = ()
    assessed_at: datetime | None = None
    assessor: str = "qedty-reference"


@dataclass(frozen=True, slots=True)
class ControlResult:
    control_id: str
    passed: bool
    rationale: str
    evidence_ids: tuple[str, ...] = ()
    severity: str = "medium"


def evaluate_controls(controls: tuple[ControlResult, ...]) -> AssuranceRecord:
    passed = all(c.passed for c in controls)
    limitations = tuple(c.rationale for c in controls if not c.passed)
    return AssuranceRecord(
        scope="governance-controls",
        passed=passed,
        evidence=tuple(sorted({e for c in controls for e in c.evidence_ids})),
        limitations=limitations,
        control_ids=tuple(c.control_id for c in controls),
    )
