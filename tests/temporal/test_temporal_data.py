from datetime import UTC, datetime

from qedty.temporal import (
    BitemporalExtent,
    SnapshotMeta,
    SnapshotSelector,
    TemporalExtent,
    TemporalGranularity,
    TemporalHistory,
    TemporalIndex,
    TemporalInstant,
    TemporalVersion,
    Timeline,
    add_granularity,
    bucket,
    floor_time,
    format_ogc_datetime,
    parse_ogc_datetime,
)


def dt(hour: int) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=UTC)


def test_granularity_hour() -> None:
    value = datetime(2026, 1, 1, 12, 42, 13, 120000, tzinfo=UTC)
    assert floor_time(value, TemporalGranularity.HOUR) == dt(12)


def test_granularity_month_and_quarter() -> None:
    value = datetime(2026, 5, 13, 8, tzinfo=UTC)
    assert floor_time(value, TemporalGranularity.MONTH) == datetime(2026, 5, 1, tzinfo=UTC)
    assert floor_time(value, TemporalGranularity.QUARTER) == datetime(2026, 4, 1, tzinfo=UTC)


def test_month_end_clamps() -> None:
    value = datetime(2026, 1, 31, 12, tzinfo=UTC)
    assert add_granularity(value, TemporalGranularity.MONTH) == datetime(
        2026, 2, 28, 12, tzinfo=UTC
    )


def test_bucket() -> None:
    start, end = bucket(datetime(2026, 1, 1, 12, 5, tzinfo=UTC), TemporalGranularity.HOUR)
    assert start == dt(12)
    assert end == dt(13)


def test_bitemporal_contains() -> None:
    x = BitemporalExtent(
        valid_time={"start": dt(0), "end": dt(4)},
        transaction_time={"start": dt(1), "end": None},
    )
    assert x.contains(valid_at=dt(2), transaction_at=dt(3))
    assert not x.contains(valid_at=dt(4), transaction_at=dt(3))


def test_temporal_instant_normalizes() -> None:
    from qedty.core.enums import TimeScale

    instant = TemporalInstant(at=datetime(2026, 1, 1, 12, tzinfo=UTC), time_scale=TimeScale.UTC)
    assert instant.at.tzinfo == UTC


def test_temporal_version_history() -> None:
    valid = TemporalExtent(start=dt(0), end=None)
    tx = TemporalExtent(start=dt(1), end=None)
    version = TemporalVersion.create(
        "grid:1", {"capacity": 100}, valid_time=valid, transaction_time=tx
    )
    history: TemporalHistory[dict[str, int]] = TemporalHistory()
    history.add(version)
    result = history.as_of(valid_at=dt(2), transaction_at=dt(2))
    assert result[0].value["capacity"] == 100


def test_snapshot_id_is_deterministic() -> None:
    selector = SnapshotSelector.at(dt(2))
    a = SnapshotMeta.create(
        world_digest="a" * 64,
        schema_version="qedty-world-model@1.0.0",
        selector=selector,
        captured_at=dt(3),
    )
    b = SnapshotMeta.create(
        world_digest="a" * 64,
        schema_version="qedty-world-model@1.0.0",
        selector=selector,
        captured_at=dt(4),
    )
    assert a.snapshot_id == b.snapshot_id


def test_temporal_index() -> None:
    index: TemporalIndex[str] = TemporalIndex()
    index.add("a", TemporalExtent(start=dt(0), end=dt(2)), "A")
    index.add("b", TemporalExtent(start=dt(3), end=dt(4)), "B")
    assert index.at(dt(1)) == ("A",)
    assert index.overlapping(TemporalExtent(start=dt(1), end=dt(3))) == ("A",)


def test_timeline_duplicate_time_sequence_is_deterministic() -> None:
    timeline: Timeline[str] = Timeline()
    timeline.put(dt(1), "first", sequence=0)
    timeline.put(dt(1), "second", sequence=1)
    assert timeline.latest() is not None
    assert timeline.latest().value == "second"


def test_ogc_datetime_parsing_and_formatting() -> None:
    parsed = parse_ogc_datetime("2026-01-01T00:00:00Z/..")
    assert isinstance(parsed, TemporalExtent)
    assert parsed.start == dt(0)
    assert parsed.end is None
    assert format_ogc_datetime(parsed) == "2026-01-01T00:00:00.000000Z/.."


def test_ogc_instant_parsing() -> None:
    parsed = parse_ogc_datetime("2026-01-01T00:00:00Z")
    assert parsed == dt(0)


def test_bitemporal_revision_selects_latest_known_transaction() -> None:
    valid = TemporalExtent(start=dt(0), end=None)
    first_tx = TemporalExtent(start=dt(1), end=dt(3))
    second_tx = TemporalExtent(start=dt(3), end=None)
    first = TemporalVersion.create(
        "grid:1", {"capacity": 90}, valid_time=valid, transaction_time=first_tx
    )
    second = TemporalVersion.create(
        "grid:1", {"capacity": 100}, valid_time=valid, transaction_time=second_tx
    )
    history: TemporalHistory[dict[str, int]] = TemporalHistory()
    history.add_many((first, second))

    before_revision = history.as_of(valid_at=dt(2), transaction_at=dt(2))
    after_revision = history.as_of(valid_at=dt(2), transaction_at=dt(3))
    assert before_revision[0].value["capacity"] == 90
    assert after_revision[0].value["capacity"] == 100
