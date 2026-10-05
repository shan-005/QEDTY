from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def in_window(instant: datetime, start: datetime | None, end: datetime | None) -> bool:
    value = ensure_utc(instant)
    if start is not None and value < ensure_utc(start):
        return False
    if end is not None and value >= ensure_utc(end):
        return False
    return True


def duration_hours(start: datetime, end: datetime) -> float:
    delta = ensure_utc(end) - ensure_utc(start)
    if delta.total_seconds() < 0:
        raise ValueError("end must not precede start")
    return delta.total_seconds() / 3600.0
