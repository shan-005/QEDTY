from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.hash import deterministic_id, sha256_hex
from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime


class ProvenanceActivity(BaseModel):
    """Qualified PROV-style activity: used entities, generated entities, agent and timing."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    provenance_id: str = Field(min_length=1, max_length=256)
    activity: str = Field(min_length=1, max_length=512)
    agent: str = Field(min_length=1, max_length=512)
    started_at: datetime
    ended_at: datetime | None = None
    used_evidence_ids: tuple[str, ...] = ()
    generated_evidence_ids: tuple[str, ...] = ()
    parent_ids: tuple[str, ...] = ()
    software_name: str | None = Field(default=None, max_length=256)
    software_version: str | None = Field(default=None, max_length=128)
    parameters_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("started_at", "ended_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not precede started_at")
        expected = deterministic_id(
            "prov",
            self.activity,
            self.agent,
            self.started_at.isoformat(),
            self.ended_at.isoformat() if self.ended_at else None,
            self.parameters_digest,
        )
        if self.provenance_id != expected:
            raise ValueError("provenance_id mismatch")
        if self.provenance_id in self.parent_ids:
            raise ValueError("provenance activity cannot parent itself")
        return self

    @classmethod
    def create(
        cls,
        *,
        activity: str,
        agent: str,
        started_at: datetime,
        parameters: Any,
        ended_at: datetime | None = None,
        used_evidence_ids: Iterable[str] = (),
        generated_evidence_ids: Iterable[str] = (),
        parent_ids: Iterable[str] = (),
        software_name: str | None = None,
        software_version: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Self:
        parameters_digest = sha256_hex(parameters)
        return cls(
            provenance_id=deterministic_id(
                "prov",
                activity,
                agent,
                ensure_utc(started_at).isoformat(),
                ensure_utc(ended_at).isoformat() if ended_at else None,
                parameters_digest,
            ),
            activity=activity,
            agent=agent,
            started_at=ensure_utc(started_at),
            ended_at=ensure_utc(ended_at) if ended_at else None,
            used_evidence_ids=tuple(sorted(set(used_evidence_ids))),
            generated_evidence_ids=tuple(sorted(set(generated_evidence_ids))),
            parent_ids=tuple(sorted(set(parent_ids))),
            software_name=software_name,
            software_version=software_version,
            parameters_digest=parameters_digest,
            metadata=metadata or {},
        )


class ProvenanceChain:
    """In-memory provenance DAG with cycle and referential-integrity checks."""

    def __init__(self) -> None:
        self._items: dict[str, ProvenanceActivity] = {}

    def add(self, item: ProvenanceActivity) -> None:
        previous = self._items.get(item.provenance_id)
        if previous is not None and previous != item:
            raise ValueError(f"provenance collision: {item.provenance_id}")
        for parent in item.parent_ids:
            if parent not in self._items:
                raise KeyError(f"unknown parent provenance: {parent}")
            if self._would_cycle(item.provenance_id, parent):
                raise ValueError("provenance cycle detected")
        self._items[item.provenance_id] = item

    def _would_cycle(self, child: str, ancestor: str) -> bool:
        if child == ancestor:
            return True
        stack = [ancestor]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current == child:
                return True
            stack.extend(self._items[current].parent_ids)
        return False

    def get(self, provenance_id: str) -> ProvenanceActivity:
        return self._items[provenance_id]

    def ancestors(self, provenance_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        stack = list(self.get(provenance_id).parent_ids)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._items[current].parent_ids)
        return tuple(sorted(seen))

    def topological(self) -> tuple[ProvenanceActivity, ...]:
        indegree = dict.fromkeys(self._items, 0)
        children: dict[str, list[str]] = {key: [] for key in self._items}
        for key, item in self._items.items():
            for parent in item.parent_ids:
                indegree[key] += 1
                children[parent].append(key)
        ready = sorted(key for key, degree in indegree.items() if degree == 0)
        ordered: list[ProvenanceActivity] = []
        while ready:
            current = ready.pop(0)
            ordered.append(self._items[current])
            for child in sorted(children[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        if len(ordered) != len(self._items):
            raise ValueError("provenance graph contains a cycle")
        return tuple(ordered)
