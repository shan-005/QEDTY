from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime


class BoundKind(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


class TemporalExtent(BaseModel):
    """Canonical half-open-compatible temporal extent with optional unbounded ends.

    QEDTY uses UTC-aware datetimes and the storage convention [start, end) for
    finite extents. Open ends are represented with ``None``. ``start`` must be
    strictly before ``end`` when both are present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    start: datetime | None = None
    end: datetime | None = None
    start_inclusive: bool = True
    end_inclusive: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> TemporalExtent:
        start = None if self.start is None else ensure_utc(self.start)
        end = None if self.end is None else ensure_utc(self.end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start is not None and end is not None and end <= start:
            raise ValueError("temporal extent requires start < end")
        if self.start_inclusive is not True or self.end_inclusive is not False:
            raise ValueError("QEDTY temporal extents use canonical [start, end) bounds")
        return self

    @classmethod
    def all_time(cls) -> TemporalExtent:
        return cls()

    @classmethod
    def half_open(cls, start: datetime, end: datetime) -> TemporalExtent:
        return cls(start=start, end=end)

    @property
    def is_bounded(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def duration_seconds(self) -> float | None:
        if not self.is_bounded:
            return None
        if self.start is None or self.end is None:
            raise ValueError("duration_seconds requires bounded start and end")
        return (self.end - self.start).total_seconds()

    def contains(self, instant: datetime) -> bool:
        t = ensure_utc(instant)
        lower = self.start is None or (t >= self.start if self.start_inclusive else t > self.start)
        upper = self.end is None or (t < self.end if not self.end_inclusive else t <= self.end)
        return lower and upper

    def contains_extent(self, other: TemporalExtent) -> bool:
        return _left_contains(self, other) and _right_contains(self, other)

    def intersects(self, other: TemporalExtent) -> bool:
        return _intersection_nonempty(self, other)

    def intersection(self, other: TemporalExtent) -> TemporalExtent | None:
        if not self.intersects(other):
            return None
        start, start_closed = _max_lower(self, other)
        end, end_closed = _min_upper(self, other)
        return TemporalExtent(
            start=start,
            end=end,
            start_inclusive=start_closed,
            end_inclusive=end_closed,
        )

    def shift_seconds(self, seconds: float) -> TemporalExtent:
        from datetime import timedelta

        delta = timedelta(seconds=seconds)
        return TemporalExtent(
            start=None if self.start is None else self.start + delta,
            end=None if self.end is None else self.end + delta,
            start_inclusive=self.start_inclusive,
            end_inclusive=self.end_inclusive,
        )

    def to_tuple(self) -> tuple[datetime | None, datetime | None, bool, bool]:
        return self.start, self.end, self.start_inclusive, self.end_inclusive


class Interval(TemporalExtent):
    """Finite proper interval used by Allen interval algebra.

    QEDTY's canonical interval storage remains [start, end); Allen relation
    classification below treats adjacency as ``MEETS`` and equality by exact
    endpoints, following Allen's interval semantics.
    """

    @model_validator(mode="after")
    def require_finite(self) -> Interval:
        if self.start is None or self.end is None:
            raise ValueError("Interval requires finite start and end")
        if not self.start_inclusive or self.end_inclusive:
            raise ValueError("Interval must use canonical [start, end) bounds")
        return self


class AllenRelation(StrEnum):
    BEFORE = "before"
    MEETS = "meets"
    OVERLAPS = "overlaps"
    STARTS = "starts"
    DURING = "during"
    FINISHES = "finishes"
    EQUALS = "equals"
    STARTED_BY = "started_by"
    CONTAINS = "contains"
    FINISHED_BY = "finished_by"
    OVERLAPPED_BY = "overlapped_by"
    MET_BY = "met_by"
    AFTER = "after"


@dataclass(frozen=True, slots=True)
class IntervalRelation:
    left: Interval
    right: Interval
    relation: AllenRelation


def classify(left: Interval, right: Interval) -> AllenRelation:
    """Return one of Allen's 13 mutually exclusive basic relations."""

    ls, le = _require_finite(left)
    rs, re = _require_finite(right)
    if le <= rs:
        return AllenRelation.MEETS if le == rs else AllenRelation.BEFORE
    if re <= ls:
        return AllenRelation.MET_BY if re == ls else AllenRelation.AFTER
    if ls == rs and le == re:
        return AllenRelation.EQUALS
    if ls == rs:
        return AllenRelation.STARTS if le < re else AllenRelation.STARTED_BY
    if le == re:
        return AllenRelation.FINISHES if ls > rs else AllenRelation.FINISHED_BY
    if rs < ls and le < re:
        return AllenRelation.DURING
    if ls < rs and re < le:
        return AllenRelation.CONTAINS
    if ls < rs < le < re:
        return AllenRelation.OVERLAPS
    return AllenRelation.OVERLAPPED_BY


def _require_finite(interval: Interval) -> tuple[datetime, datetime]:
    if interval.start is None or interval.end is None:
        raise ValueError("finite interval required")
    return interval.start, interval.end


def _intersection_nonempty(left: TemporalExtent, right: TemporalExtent) -> bool:
    start, start_closed = _max_lower(left, right)
    end, end_closed = _min_upper(left, right)
    if start is None or end is None:
        return True
    if start < end:
        return True
    return start == end and start_closed and end_closed


def _max_lower(a: TemporalExtent, b: TemporalExtent) -> tuple[datetime | None, bool]:
    if a.start is None:
        return b.start, b.start_inclusive
    if b.start is None:
        return a.start, a.start_inclusive
    if a.start > b.start:
        return a.start, a.start_inclusive
    if b.start > a.start:
        return b.start, b.start_inclusive
    return a.start, a.start_inclusive and b.start_inclusive


def _min_upper(a: TemporalExtent, b: TemporalExtent) -> tuple[datetime | None, bool]:
    if a.end is None:
        return b.end, b.end_inclusive
    if b.end is None:
        return a.end, a.end_inclusive
    if a.end < b.end:
        return a.end, a.end_inclusive
    if b.end < a.end:
        return b.end, b.end_inclusive
    return a.end, a.end_inclusive and b.end_inclusive


def _left_contains(container: TemporalExtent, inner: TemporalExtent) -> bool:
    if container.start is None:
        return True
    if inner.start is None:
        return False
    if inner.start > container.start:
        return True
    if inner.start < container.start:
        return False
    return container.start_inclusive or not inner.start_inclusive


def _right_contains(container: TemporalExtent, inner: TemporalExtent) -> bool:
    if container.end is None:
        return True
    if inner.end is None:
        return False
    if inner.end < container.end:
        return True
    if inner.end > container.end:
        return False
    return container.end_inclusive or not inner.end_inclusive
