from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from seraph.core.hash import sha256_hex


@dataclass(frozen=True, slots=True)
class FusionRecord:
    subject_id: str
    attributes: dict[str, object]
    evidence_ids: tuple[str, ...]
    confidence: float
    provenance_ids: tuple[str, ...] = ()
    conflict_score: float = 0.0

    def validate(self) -> None:
        if not self.subject_id.strip():
            raise ValueError("subject_id empty")
        if not 0 <= self.confidence <= 1 or not 0 <= self.conflict_score <= 1:
            raise ValueError("confidence/conflict out of range")

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_hex(self)


def fuse(records: list[FusionRecord]) -> FusionRecord:
    if not records:
        raise ValueError("no records")
    subject_ids = {r.subject_id for r in records}
    if len(subject_ids) != 1:
        raise ValueError("cannot fuse different subjects")
    for r in records:
        r.validate()
    keys = sorted({k for r in records for k in r.attributes})
    attrs: dict[str, object] = {}
    conflicts = 0
    for key in keys:
        present = [r.attributes[key] for r in records if key in r.attributes]
        attrs[key] = present[0]
        if any(v != present[0] for v in present[1:]):
            conflicts += 1
    ids = tuple(sorted({i for r in records for i in r.evidence_ids}))
    prov = tuple(sorted({i for r in records for i in r.provenance_ids}))
    confidence = sum(r.confidence for r in records) / len(records)
    conflict_score = conflicts / len(keys) if keys else 0.0
    confidence *= 1.0 - 0.5 * conflict_score
    return FusionRecord(records[0].subject_id, attrs, ids, confidence, prov, conflict_score)


def weighted_numeric(values: list[tuple[float, float]]) -> tuple[float, float]:
    """Precision-like fusion: (estimate, confidence) from (value, confidence)."""
    if not values:
        raise ValueError("values empty")
    if any(not isfinite(v) or not 0 <= w <= 1 for v, w in values):
        raise ValueError("invalid values/confidences")
    total = sum(w for _, w in values)
    if total <= 0:
        return (sum(v for v, _ in values) / len(values), 0.0)
    estimate = sum(v * w for v, w in values) / total
    disagreement = sum(w * abs(v - estimate) for v, w in values) / total
    confidence = max(0.0, 1.0 - disagreement / (abs(estimate) + 1.0))
    return estimate, confidence
