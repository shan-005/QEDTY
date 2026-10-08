from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .intervals import TemporalExtent

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class IndexedInterval[T]:
    key: str
    extent: TemporalExtent
    value: T


class TemporalIndex[T]:
    """Reference temporal index with deterministic ordering and overlap scans.

    The Python implementation intentionally remains backend-neutral. A later
    Rust/PostgreSQL implementation can replace the index while preserving this
    query contract.
    """

    def __init__(self) -> None:
        self._items: dict[str, IndexedInterval[T]] = {}
        self._starts: list[tuple[datetime | None, str]] = []
        self._lock = RLock()

    def add(self, key: str, extent: TemporalExtent, value: T) -> None:
        with self._lock:
            previous = self._items.get(key)
            if previous is not None:
                if previous.extent != extent or previous.value != value:
                    raise ValueError(f"temporal index collision: {key}")
                return
            self._items[key] = IndexedInterval(key, extent, value)
            self._starts.append((extent.start, key))
            self._starts.sort(
                key=lambda item: (item[0] is not None, item[0] or datetime.min, item[1])
            )

    def remove(self, key: str) -> IndexedInterval[T]:
        with self._lock:
            item = self._items.pop(key)
            self._starts = [pair for pair in self._starts if pair[1] != key]
            return item

    def get(self, key: str) -> IndexedInterval[T]:
        with self._lock:
            return self._items[key]

    def overlapping(self, query: TemporalExtent) -> tuple[T, ...]:
        with self._lock:
            return tuple(
                item.value for item in self._items.values() if item.extent.intersects(query)
            )

    def at(self, instant: datetime) -> tuple[T, ...]:
        with self._lock:
            return tuple(
                item.value for item in self._items.values() if item.extent.contains(instant)
            )

    def all(self) -> tuple[IndexedInterval[T], ...]:
        with self._lock:
            return tuple(
                self._items[key]
                for _, key in sorted(
                    self._starts,
                    key=lambda item: (item[0] is not None, item[0] or datetime.min, item[1]),
                )
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._starts.clear()
