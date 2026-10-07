from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING

from seraph.core.errors import StorageError

if TYPE_CHECKING:
    from datetime import datetime

    from .models import EvidenceRecord


class EvidenceRegistry:
    """Thread-safe evidence index with digest/source secondary indexes."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceRecord] = {}
        self._by_digest: dict[str, set[str]] = {}
        self._by_source: dict[str, set[str]] = {}
        self._lock = RLock()

    def add(self, item: EvidenceRecord) -> None:
        with self._lock:
            previous = self._items.get(item.evidence_id)
            if previous is not None and previous != item:
                raise StorageError(f"evidence collision: {item.evidence_id}")
            if previous is not None:
                return
            self._items[item.evidence_id] = item
            self._by_digest.setdefault(item.content_sha256, set()).add(item.evidence_id)
            self._by_source.setdefault(item.source.source_id, set()).add(item.evidence_id)

    def get(self, evidence_id: str) -> EvidenceRecord:
        with self._lock:
            try:
                return self._items[evidence_id]
            except KeyError as exc:
                raise StorageError(f"evidence not found: {evidence_id}") from exc

    def by_digest(self, digest: str) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(
                self._items[key] for key in sorted(self._by_digest.get(digest.lower(), set()))
            )

    def by_source(self, source_id: str) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(self._items[key] for key in sorted(self._by_source.get(source_id, set())))

    def all(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(self._items[key] for key in sorted(self._items))

    def by_entity(self, entity_id: str) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(
                item
                for item in self.all()
                if any(ref.entity_id == entity_id for ref in item.about_entities)
            )

    def containing(self, instant: datetime) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(
                item
                for item in self.all()
                if item.valid_time is not None and item.valid_time.contains(instant)
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
