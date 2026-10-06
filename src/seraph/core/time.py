from __future__ import annotations
from datetime import UTC, datetime, timedelta

def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None: raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)

def now_utc() -> datetime: return datetime.now(UTC)

def in_window(instant: datetime, start: datetime|None, end: datetime|None) -> bool:
    t=ensure_utc(instant)
    return (start is None or t>=ensure_utc(start)) and (end is None or t<ensure_utc(end))

def hours(start: datetime,end: datetime)->float:
    d=ensure_utc(end)-ensure_utc(start)
    if d.total_seconds()<0: raise ValueError("end precedes start")
    return d.total_seconds()/3600.0

def add_hours(value: datetime, delta: float)->datetime: return ensure_utc(value)+timedelta(hours=delta)
