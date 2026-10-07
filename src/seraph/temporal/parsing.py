from __future__ import annotations

from datetime import datetime

from seraph.core.time import ensure_utc, parse_rfc3339, to_rfc3339

from .intervals import TemporalExtent


class TemporalParseError(ValueError):
    """Raised when an external temporal interval cannot be parsed."""


def parse_ogc_datetime(value: str) -> datetime | TemporalExtent:
    """Parse an OGC-style ``datetime`` parameter.

    Accepted forms are an RFC3339 instant, a bounded interval, a half-bounded
    interval using ``..``, or the fully unbounded ``../..`` interval.
    """

    token = value.strip()
    if not token:
        raise TemporalParseError("datetime parameter is empty")
    if "/" not in token:
        return parse_rfc3339(token)

    parts = token.split("/")
    if len(parts) != 2:
        raise TemporalParseError("datetime interval must contain exactly one slash")
    left, right = parts
    start = None if left in {"", ".."} else ensure_utc(parse_rfc3339(left))
    end = None if right in {"", ".."} else ensure_utc(parse_rfc3339(right))
    if start is None and end is None:
        return TemporalExtent.all_time()
    if start is not None and end is not None and end <= start:
        raise TemporalParseError("interval end must be after start")
    return TemporalExtent(start=start, end=end)


def format_ogc_datetime(value: datetime | TemporalExtent) -> str:
    """Serialize an instant or extent using an OGC-compatible datetime form."""

    if isinstance(value, datetime):
        return to_rfc3339(ensure_utc(value))
    left = ".." if value.start is None else to_rfc3339(value.start)
    right = ".." if value.end is None else to_rfc3339(value.end)
    return f"{left}/{right}"
