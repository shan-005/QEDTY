from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Final

from .errors import TemporalError

UNIX_EPOCH: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)
UTC_MIN: Final[datetime] = datetime.min.replace(tzinfo=UTC)
UTC_MAX: Final[datetime] = datetime.max.replace(tzinfo=UTC)
NANOSECONDS_PER_SECOND: Final[int] = 1_000_000_000


def ensure_utc(value: datetime) -> datetime:
    """Require an aware datetime and normalize its instant to UTC.

    SERAPH deliberately rejects naive datetimes because Python documents that
    naive datetimes cannot identify an unambiguous instant. Arrow and protobuf
    also define timezone-aware timestamps in terms of UTC-normalized instants.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise TemporalError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def now_utc() -> datetime:
    """Return the current UTC instant."""
    return datetime.now(UTC)


def parse_rfc3339(value: str) -> datetime:
    """Parse an RFC 3339/ISO-8601 timestamp and return UTC.

    RFC 3339 uses ``Z`` for UTC; Python's ``fromisoformat`` also accepts the
    explicit ``+00:00`` form. SERAPH never returns naive datetimes.
    """
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return ensure_utc(datetime.fromisoformat(text))
    except ValueError as exc:
        raise TemporalError(f"invalid RFC 3339 timestamp: {value!r}") from exc


def to_rfc3339(value: datetime, *, timespec: str = "microseconds") -> str:
    """Serialize an aware instant in UTC using a stable ``Z`` suffix."""
    return ensure_utc(value).isoformat(timespec=timespec).replace("+00:00", "Z")


def in_window(instant: datetime, start: datetime | None, end: datetime | None) -> bool:
    """Test membership in a half-open interval ``[start, end)``."""
    t = ensure_utc(instant)
    s = ensure_utc(start) if start is not None else None
    e = ensure_utc(end) if end is not None else None
    if s is not None and e is not None and e <= s:
        raise TemporalError("window end must be after start")
    return (s is None or t >= s) and (e is None or t < e)


def validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Normalize and validate a non-empty half-open window."""
    s, e = ensure_utc(start), ensure_utc(end)
    if e <= s:
        raise TemporalError("window end must be after start")
    return s, e


def seconds(start: datetime, end: datetime) -> float:
    """Return elapsed SI seconds between two aware instants."""
    d = ensure_utc(end) - ensure_utc(start)
    if d.total_seconds() < 0:
        raise TemporalError("end precedes start")
    return d.total_seconds()


def hours(start: datetime, end: datetime) -> float:
    """Return elapsed hours between two aware instants."""
    return seconds(start, end) / 3600.0


def days(start: datetime, end: datetime) -> float:
    """Return elapsed days between two aware instants."""
    return seconds(start, end) / 86400.0


def add_seconds(value: datetime, delta: int | float | Decimal) -> datetime:
    """Add elapsed seconds to an aware instant at Python datetime precision."""
    microseconds = int(
        (Decimal(str(delta)) * Decimal(1_000_000)).to_integral_value(rounding=ROUND_HALF_EVEN)
    )
    return ensure_utc(value) + timedelta(microseconds=microseconds)


def add_hours(value: datetime, delta: float) -> datetime:
    """Add elapsed hours to an aware instant."""
    return add_seconds(value, delta * 3600.0)


def unix_seconds(value: datetime) -> Decimal:
    """Return POSIX seconds as Decimal without losing microsecond precision."""
    instant = ensure_utc(value)
    delta = instant - UNIX_EPOCH
    return Decimal(delta.days * 86400 + delta.seconds) + (
        Decimal(delta.microseconds) / Decimal(1_000_000)
    )


def from_unix_seconds(value: int | float | Decimal) -> datetime:
    """Construct a UTC datetime from POSIX seconds without float-only math."""
    try:
        total = Decimal(str(value))
        whole = total.to_integral_value(rounding=ROUND_FLOOR)
        fraction = total - whole
        micros = int((fraction * Decimal(1_000_000)).to_integral_value(rounding=ROUND_HALF_EVEN))
        if micros == 1_000_000:
            whole += 1
            micros = 0
        return UNIX_EPOCH + timedelta(seconds=int(whole), microseconds=micros)
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise TemporalError(f"invalid Unix timestamp: {value!r}") from exc


def midpoint(start: datetime, end: datetime) -> datetime:
    """Return the temporal midpoint of a validated interval."""
    return add_seconds(ensure_utc(start), seconds(start, end) / 2.0)


def clamp(value: datetime, start: datetime, end: datetime) -> datetime:
    """Clamp an instant to the closed interval ``[start, end]``."""
    s, e = ensure_utc(start), ensure_utc(end)
    if e < s:
        raise TemporalError("clamp end must not precede start")
    v = ensure_utc(value)
    return max(s, min(v, e))


def calendar_date(value: datetime) -> date:
    """Return the UTC calendar date of an aware instant."""
    return ensure_utc(value).date()
