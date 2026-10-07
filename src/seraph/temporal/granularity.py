from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from enum import StrEnum

from seraph.core.time import ensure_utc


class TemporalGranularity(StrEnum):
    MICROSECOND = "microsecond"
    MILLISECOND = "millisecond"
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


def floor_time(value: datetime, granularity: TemporalGranularity) -> datetime:
    value = ensure_utc(value)
    if granularity is TemporalGranularity.MICROSECOND:
        return value
    if granularity is TemporalGranularity.MILLISECOND:
        return value.replace(microsecond=(value.microsecond // 1_000) * 1_000)
    if granularity is TemporalGranularity.SECOND:
        return value.replace(microsecond=0)
    if granularity is TemporalGranularity.MINUTE:
        return value.replace(second=0, microsecond=0)
    if granularity is TemporalGranularity.HOUR:
        return value.replace(minute=0, second=0, microsecond=0)
    if granularity is TemporalGranularity.DAY:
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity is TemporalGranularity.WEEK:
        day = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())
    if granularity is TemporalGranularity.MONTH:
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity is TemporalGranularity.QUARTER:
        month = ((value.month - 1) // 3) * 3 + 1
        return value.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
    return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def add_granularity(value: datetime, granularity: TemporalGranularity, count: int = 1) -> datetime:
    value = ensure_utc(value)
    if granularity is TemporalGranularity.MICROSECOND:
        return value + timedelta(microseconds=count)
    if granularity is TemporalGranularity.MILLISECOND:
        return value + timedelta(milliseconds=count)
    if granularity is TemporalGranularity.SECOND:
        return value + timedelta(seconds=count)
    if granularity is TemporalGranularity.MINUTE:
        return value + timedelta(minutes=count)
    if granularity is TemporalGranularity.HOUR:
        return value + timedelta(hours=count)
    if granularity is TemporalGranularity.DAY:
        return value + timedelta(days=count)
    if granularity is TemporalGranularity.WEEK:
        return value + timedelta(weeks=count)
    months = count * (
        3
        if granularity is TemporalGranularity.QUARTER
        else 1
        if granularity is TemporalGranularity.MONTH
        else 12
    )
    index = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def bucket(value: datetime, granularity: TemporalGranularity) -> tuple[datetime, datetime]:
    start = floor_time(value, granularity)
    return start, add_granularity(start, granularity)
