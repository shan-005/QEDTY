from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from seraph.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class TimelinePoint[T]:
    at: datetime
    value: T
    sequence: int = 0

    def normalized(self) -> TimelinePoint[T]:
        return TimelinePoint(ensure_utc(self.at), self.value, self.sequence)


@dataclass
class Timeline[T]:
    """Deterministic event/value timeline supporting duplicate-time ordering."""

    _points: list[TimelinePoint[T]] = field(default_factory=list)

    def put(self, at: datetime, value: T, *, sequence: int | None = None) -> None:
        point = TimelinePoint(
            ensure_utc(at), value, len(self._points) if sequence is None else sequence
        )
        self._points.append(point)
        self._points.sort(key=lambda item: (item.at, item.sequence))

    def at_or_before(self, at: datetime) -> T | None:
        t = ensure_utc(at)
        candidates = [point for point in self._points if point.at <= t]
        return candidates[-1].value if candidates else None

    def at_or_after(self, at: datetime) -> T | None:
        t = ensure_utc(at)
        candidates = [point for point in self._points if point.at >= t]
        return candidates[0].value if candidates else None

    def between(
        self, start: datetime, end: datetime, *, include_end: bool = False
    ) -> tuple[TimelinePoint[T], ...]:
        s = ensure_utc(start)
        e = ensure_utc(end)
        if e < s:
            raise ValueError("end must not precede start")
        if include_end:
            return tuple(point for point in self._points if s <= point.at <= e)
        return tuple(point for point in self._points if s <= point.at < e)

    def latest(self) -> TimelinePoint[T] | None:
        return self._points[-1] if self._points else None

    def ordered(self) -> tuple[TimelinePoint[T], ...]:
        return tuple(self._points)

    def values(self) -> tuple[T, ...]:
        return tuple(point.value for point in self._points)

    def __len__(self) -> int:
        return len(self._points)
