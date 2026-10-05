from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from seraph.core.time import ensure_utc


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    provenance_id: str = Field(min_length=1, max_length=256)
    activity: str = Field(min_length=1, max_length=512)
    agent: str = Field(min_length=1, max_length=512)
    started_at: datetime
    ended_at: datetime | None = None
    used_evidence_ids: tuple[str, ...] = ()
    generated_entity_ids: tuple[str, ...] = ()
    generated_relationship_ids: tuple[str, ...] = ()
    parent_provenance_ids: tuple[str, ...] = ()
    software_version: str = Field(min_length=1, max_length=128)
    parameters_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @field_validator("started_at", "ended_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @property
    def is_closed(self) -> bool:
        return self.ended_at is not None


class ProvenanceChain:
    def __init__(self) -> None:
        self._records: dict[str, Provenance] = {}

    def add(self, record: Provenance) -> None:
        if record.provenance_id in self._records and self._records[record.provenance_id] != record:
            raise ValueError(f"provenance conflict: {record.provenance_id}")
        for parent_id in record.parent_provenance_ids:
            if parent_id == record.provenance_id:
                raise ValueError("provenance record cannot parent itself")
            if parent_id not in self._records:
                raise KeyError(f"unknown parent provenance: {parent_id}")
        self._records[record.provenance_id] = record

    def get(self, provenance_id: str) -> Provenance:
        return self._records[provenance_id]

    def all(self) -> tuple[Provenance, ...]:
        return tuple(sorted(self._records.values(), key=lambda r: r.provenance_id))

    def ancestors(self, provenance_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        stack = list(self.get(provenance_id).parent_provenance_ids)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.get(current).parent_provenance_ids)
        return tuple(sorted(seen))
