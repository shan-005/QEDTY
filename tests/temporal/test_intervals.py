from datetime import UTC, datetime

import pytest

from qedty.temporal import AllenRelation, Interval, TemporalExtent, classify


def d(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (Interval(start=d(1), end=d(2)), Interval(start=d(3), end=d(4)), AllenRelation.BEFORE),
        (Interval(start=d(1), end=d(2)), Interval(start=d(2), end=d(3)), AllenRelation.MEETS),
        (Interval(start=d(1), end=d(3)), Interval(start=d(2), end=d(4)), AllenRelation.OVERLAPS),
        (Interval(start=d(1), end=d(3)), Interval(start=d(1), end=d(4)), AllenRelation.STARTS),
        (Interval(start=d(2), end=d(3)), Interval(start=d(1), end=d(4)), AllenRelation.DURING),
        (Interval(start=d(2), end=d(4)), Interval(start=d(1), end=d(4)), AllenRelation.FINISHES),
        (Interval(start=d(1), end=d(2)), Interval(start=d(1), end=d(2)), AllenRelation.EQUALS),
    ],
)
def test_allen_relations(left: Interval, right: Interval, expected: AllenRelation) -> None:
    assert classify(left, right) is expected


def test_open_ended_extent_and_intersection() -> None:
    left = TemporalExtent(start=d(1), end=None)
    right = TemporalExtent(start=d(3), end=d(4))
    intersection = left.intersection(right)
    assert intersection is not None
    assert intersection.start == d(3)
    assert intersection.end == d(4)


def test_half_open_boundary() -> None:
    extent = TemporalExtent(start=d(1), end=d(2))
    assert extent.contains(d(1))
    assert not extent.contains(d(2))


def test_shift() -> None:
    extent = TemporalExtent(start=d(1), end=d(2))
    shifted = extent.shift_seconds(3600)
    assert shifted.start == d(1, 1)
    assert shifted.end == d(2, 1)


def test_invalid_interval() -> None:
    with pytest.raises(ValueError):
        TemporalExtent(start=d(2), end=d(1))


def test_interval_requires_finite_bounds() -> None:
    with pytest.raises(ValueError):
        Interval(start=d(1), end=None)


def test_allen_inverse_is_consistent() -> None:
    from qedty.temporal import inverse

    cases = {
        AllenRelation.BEFORE: (Interval(start=d(1), end=d(2)), Interval(start=d(3), end=d(4))),
        AllenRelation.MEETS: (Interval(start=d(1), end=d(2)), Interval(start=d(2), end=d(3))),
        AllenRelation.OVERLAPS: (Interval(start=d(1), end=d(3)), Interval(start=d(2), end=d(4))),
        AllenRelation.STARTS: (Interval(start=d(1), end=d(2)), Interval(start=d(1), end=d(3))),
        AllenRelation.DURING: (Interval(start=d(2), end=d(3)), Interval(start=d(1), end=d(4))),
        AllenRelation.FINISHES: (Interval(start=d(2), end=d(4)), Interval(start=d(1), end=d(4))),
        AllenRelation.EQUALS: (Interval(start=d(1), end=d(2)), Interval(start=d(1), end=d(2))),
        AllenRelation.STARTED_BY: (Interval(start=d(1), end=d(3)), Interval(start=d(1), end=d(2))),
        AllenRelation.CONTAINS: (Interval(start=d(1), end=d(4)), Interval(start=d(2), end=d(3))),
        AllenRelation.FINISHED_BY: (Interval(start=d(1), end=d(4)), Interval(start=d(2), end=d(4))),
        AllenRelation.OVERLAPPED_BY: (
            Interval(start=d(2), end=d(4)),
            Interval(start=d(1), end=d(3)),
        ),
        AllenRelation.MET_BY: (Interval(start=d(2), end=d(3)), Interval(start=d(1), end=d(2))),
        AllenRelation.AFTER: (Interval(start=d(3), end=d(4)), Interval(start=d(1), end=d(2))),
    }
    for expected, (left, right) in cases.items():
        assert classify(left, right) is expected
        assert classify(right, left) is inverse(expected)
