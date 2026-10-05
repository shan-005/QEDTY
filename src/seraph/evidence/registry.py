from __future__ import annotations

from collections.abc import Iterable

from seraph.evidence.models import EvidenceRecord


class EvidenceRegistry:
    """Content-addressed evidence registry with deterministic collision checks."""

    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: EvidenceRecord) -> None:
        existing = self._records.get(record.evidence_id)
        if existing is not None and existing != record:
            raise ValueError(f"evidence collision: {record.evidence_id}")
        self._records[record.evidence_id] = record

    def get(self, evidence_id: str) -> EvidenceRecord:
        return self._records[evidence_id]

    def require_all(self, evidence_ids: Iterable[str]) -> tuple[EvidenceRecord, ...]:
        ids = tuple(dict.fromkeys(evidence_ids))
        missing = sorted(set(ids) - self._records.keys())
        if missing:
            raise KeyError(f"unknown evidence ids: {missing}")
        return tuple(self._records[evidence_id] for evidence_id in ids)

    def all(self) -> tuple[EvidenceRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda r: r.evidence_id))

    def __len__(self) -> int:
        return len(self._records)
