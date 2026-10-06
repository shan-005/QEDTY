from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionRecord:
    subject_id: str
    attributes: dict[str, object]
    evidence_ids: tuple[str, ...]
    confidence: float

    def validate(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence out of range")


def fuse(records: list[FusionRecord]) -> FusionRecord:
    if not records:
        raise ValueError("no records")
    keys = sorted({k for r in records for k in r.attributes})
    attrs = {k: next((r.attributes[k] for r in records if k in r.attributes), None) for k in keys}
    ids = tuple(sorted({i for r in records for i in r.evidence_ids}))
    conf = sum(r.confidence for r in records) / len(records)
    return FusionRecord(records[0].subject_id, attrs, ids, conf)
