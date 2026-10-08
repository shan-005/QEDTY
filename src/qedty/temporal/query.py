from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from qedty.core.time import ensure_utc

from .intervals import Interval, TemporalExtent

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from datetime import datetime

    from qedty.core.types import TimeWindow
    from qedty.ontology.relations import Relationship

T = TypeVar("T")
U = TypeVar("U")


def active_at(extent: TemporalExtent | TimeWindow | None, at: datetime) -> bool:
    if extent is None:
        return True
    return extent.contains(ensure_utc(at))


def active_relationships(edges: Iterable[Relationship], at: datetime) -> tuple[Relationship, ...]:
    return tuple(edge for edge in edges if active_at(edge.valid_time, at))


def overlaps(a: TemporalExtent, b: TemporalExtent) -> bool:
    return a.intersects(b)


def contains(extent: TemporalExtent, instant: datetime) -> bool:
    return extent.contains(instant)


def select_at[T](
    records: Iterable[T], instant: datetime, extent_of: Callable[[T], TemporalExtent | None]
) -> tuple[T, ...]:
    return tuple(item for item in records if active_at(extent_of(item), instant))


def select_overlapping[T](
    records: Iterable[T],
    query_extent: TemporalExtent,
    extent_of: Callable[[T], TemporalExtent],
) -> tuple[T, ...]:
    return tuple(item for item in records if extent_of(item).intersects(query_extent))


def temporal_join[T, U](
    left: Sequence[T],
    right: Sequence[U],
    left_extent: Callable[[T], TemporalExtent],
    right_extent: Callable[[U], TemporalExtent],
) -> tuple[tuple[T, U, TemporalExtent], ...]:
    joined: list[tuple[T, U, TemporalExtent]] = []
    for left_item in left:
        for right_item in right:
            intersection = left_extent(left_item).intersection(right_extent(right_item))
            if intersection is not None:
                joined.append((left_item, right_item, intersection))
    return tuple(joined)


def to_interval(extent: TemporalExtent) -> Interval:
    if extent.start is None or extent.end is None:
        raise ValueError("finite interval required")
    return Interval(start=extent.start, end=extent.end)
