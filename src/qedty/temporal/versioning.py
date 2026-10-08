from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import TemporalVersion

T = TypeVar("T")


class TemporalHistory[T]:
    """Append-only bitemporal reference history.

    ``as_of`` selects records true at ``valid_at`` according to the state known
    at ``transaction_at``. When multiple versions remain applicable, the one
    with the latest transaction start is authoritative for that historical view.
    """

    def __init__(self) -> None:
        self._versions: dict[str, TemporalVersion[T]] = {}
        self._lock = RLock()

    def add(self, version: TemporalVersion[T]) -> None:
        with self._lock:
            previous = self._versions.get(version.version_id)
            if previous is not None and previous != version:
                raise ValueError(f"version collision: {version.version_id}")
            self._versions[version.version_id] = version

    def add_many(self, versions: Iterable[TemporalVersion[T]]) -> None:
        for version in versions:
            self.add(version)

    def get(self, version_id: str) -> TemporalVersion[T]:
        with self._lock:
            return self._versions[version_id]

    def all(self) -> tuple[TemporalVersion[T], ...]:
        with self._lock:
            return tuple(sorted(self._versions.values(), key=lambda value: value.version_id))

    def as_of(
        self, *, valid_at: datetime, transaction_at: datetime
    ) -> tuple[TemporalVersion[T], ...]:
        with self._lock:
            candidates = [
                version
                for version in self._versions.values()
                if (
                    version.valid_time.contains(valid_at)
                    and version.transaction_time.contains(transaction_at)
                )
            ]
            grouped: dict[str, list[TemporalVersion[T]]] = {}
            for version in candidates:
                grouped.setdefault(version.record_key, []).append(version)
            chosen: list[TemporalVersion[T]] = []
            for versions in grouped.values():
                versions.sort(
                    key=lambda item: (
                        item.transaction_time.start or datetime.min.replace(tzinfo=valid_at.tzinfo),
                        item.version_id,
                    ),
                    reverse=True,
                )
                chosen.append(versions[0])
            return tuple(sorted(chosen, key=lambda item: item.record_key))

    def latest_known(self, record_key: str, transaction_at: datetime) -> TemporalVersion[T] | None:
        values = [
            item
            for item in self._versions.values()
            if item.record_key == record_key and item.transaction_time.contains(transaction_at)
        ]
        if not values:
            return None
        values.sort(
            key=lambda item: (
                item.transaction_time.start or datetime.min.replace(tzinfo=transaction_at.tzinfo),
                item.version_id,
            ),
            reverse=True,
        )
        return values[0]
