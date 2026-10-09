//! RFC 3339 timestamp normalization and half-open temporal intervals.
//!
//! This module implements the timestamp subset used by QEDTY's Python reference
//! without introducing a new dependency into the native core. Instants are stored
//! as Unix seconds plus microseconds because Python datetime has microsecond
//! precision. Fractional input beyond six digits is truncated, matching
//! datetime.fromisoformat.

use thiserror::Error;

const SECONDS_PER_DAY: i64 = 86_400;

/// A UTC instant with the same microsecond precision as QEDTY's Python reference.
/// The private fields prevent invalid microsecond values.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct UtcInstant {
    unix_seconds: i64,
    microseconds: u32,
}

impl UtcInstant {
    /// Whole Unix seconds, using floor-based normalization before the epoch.
    pub const fn unix_seconds(self) -> i64 {
        self.unix_seconds
    }

    /// Microseconds within the current second, always in 0..1_000_000.
    pub const fn microseconds(self) -> u32 {
        self.microseconds
    }
}

/// Errors for timestamp parsing, UTC normalization, and interval validation.
#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum TemporalError {
    #[error("timestamp is not a supported RFC 3339 date-time")]
    InvalidTimestamp,
    #[error("timestamp must include a timezone designator")]
    MissingTimezone,
    #[error("date is invalid or outside Python datetime's years 0001..9999")]
    InvalidDate,
    #[error("time-of-day is invalid")]
    InvalidTime,
    #[error("timezone offset must use ±HH:MM and be within ±23:59")]
    InvalidOffset,
    #[error("normalized UTC instant is outside Python datetime's years 0001..9999")]
    UtcOutOfRange,
    #[error("interval end must be strictly after its start")]
    InvalidInterval,
}

/// Parse a timezone-aware RFC 3339 date-time and normalize it to UTC.
///
/// The parser accepts Z and numeric ±HH:MM offsets. Fractional input precision
/// beyond microseconds is truncated, matching Python datetime.fromisoformat.
/// Naive timestamps are rejected.
pub fn parse_rfc3339(input: &str) -> Result<UtcInstant, TemporalError> {
    let text = input.trim();
    if text.is_empty() || !text.is_ascii() {
        return Err(TemporalError::InvalidTimestamp);
    }

    let (local, offset_seconds) = if let Some(local) = text.strip_suffix('Z') {
        (local, 0_i64)
    } else {
        let offset_start = text
            .char_indices()
            .filter(|(index, character)| *index >= 10 && (*character == '+' || *character == '-'))
            .map(|(index, _)| index)
            .next_back()
            .ok_or(TemporalError::MissingTimezone)?;
        let offset_seconds = parse_offset(&text[offset_start..])?;
        (&text[..offset_start], offset_seconds)
    };

    let (year, month, day, hour, minute, second, microseconds) = parse_local_datetime(local)?;
    let days = days_from_civil(year, month, day);
    let local_seconds =
        days * 86_400 + i64::from(hour) * 3_600 + i64::from(minute) * 60 + i64::from(second);
    let unix_seconds = local_seconds - offset_seconds;

    ensure_supported_utc_year(unix_seconds)?;

    Ok(UtcInstant {
        unix_seconds,
        microseconds,
    })
}

/// Serialize a UTC instant using a fixed six-digit fractional second and Z.
pub fn to_rfc3339(value: UtcInstant) -> Result<String, TemporalError> {
    let days = value.unix_seconds.div_euclid(SECONDS_PER_DAY);
    let seconds_of_day = value.unix_seconds.rem_euclid(SECONDS_PER_DAY);
    let (year, month, day) = civil_from_days(days);
    if !(1..=9999).contains(&year) {
        return Err(TemporalError::UtcOutOfRange);
    }

    let hour = seconds_of_day / 3_600;
    let minute = (seconds_of_day % 3_600) / 60;
    let second = seconds_of_day % 60;
    Ok(format!(
        "{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{:06}Z",
        value.microseconds
    ))
}

/// A validated non-empty half-open interval, [start, end).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TimeInterval {
    pub start: UtcInstant,
    pub end: UtcInstant,
}

impl TimeInterval {
    /// Construct an interval whose end is strictly later than its start.
    pub fn new(start: UtcInstant, end: UtcInstant) -> Result<Self, TemporalError> {
        if end <= start {
            return Err(TemporalError::InvalidInterval);
        }
        Ok(Self { start, end })
    }

    /// Return whether instant belongs to [start, end).
    pub fn contains(self, instant: UtcInstant) -> bool {
        instant >= self.start && instant < self.end
    }

    /// Return the non-empty overlap with another interval, if one exists.
    pub fn intersection(self, other: Self) -> Option<Self> {
        let start = self.start.max(other.start);
        let end = self.end.min(other.end);
        (start < end).then_some(Self { start, end })
    }
}

/// Test membership in a half-open interval with optional unbounded endpoints.
///
/// If both endpoints exist, end must be strictly later than start.
pub fn in_window(
    instant: UtcInstant,
    start: Option<UtcInstant>,
    end: Option<UtcInstant>,
) -> Result<bool, TemporalError> {
    if let (Some(start), Some(end)) = (start, end) {
        if end <= start {
            return Err(TemporalError::InvalidInterval);
        }
    }
    Ok(start.map_or(true, |start| instant >= start) && end.map_or(true, |end| instant < end))
}

/// Validate and return a non-empty half-open interval.
pub fn validate_window(start: UtcInstant, end: UtcInstant) -> Result<TimeInterval, TemporalError> {
    TimeInterval::new(start, end)
}

fn parse_offset(text: &str) -> Result<i64, TemporalError> {
    let bytes = text.as_bytes();
    if bytes.len() != 6 || (bytes[0] != b'+' && bytes[0] != b'-') || bytes[3] != b':' {
        return Err(TemporalError::InvalidOffset);
    }
    let hours = parse_digits(bytes, 1, 3).map_err(|_| TemporalError::InvalidOffset)?;
    let minutes = parse_digits(bytes, 4, 6).map_err(|_| TemporalError::InvalidOffset)?;
    if hours > 23 || minutes > 59 {
        return Err(TemporalError::InvalidOffset);
    }
    let magnitude = i64::from(hours) * 3_600 + i64::from(minutes) * 60;
    Ok(if bytes[0] == b'-' {
        -magnitude
    } else {
        magnitude
    })
}

fn parse_local_datetime(text: &str) -> Result<(i32, u32, u32, u32, u32, u32, u32), TemporalError> {
    let bytes = text.as_bytes();
    if !text.is_ascii()
        || bytes.len() < 19
        || bytes[4] != b'-'
        || bytes[7] != b'-'
        || !matches!(bytes[10], b'T' | b't' | b' ')
        || bytes[13] != b':'
        || bytes[16] != b':'
    {
        return Err(TemporalError::InvalidTimestamp);
    }

    let year = parse_digits(bytes, 0, 4)? as i32;
    let month = parse_digits(bytes, 5, 7)?;
    let day = parse_digits(bytes, 8, 10)?;
    let hour = parse_digits(bytes, 11, 13)?;
    let minute = parse_digits(bytes, 14, 16)?;
    let second = parse_digits(bytes, 17, 19)?;

    if year == 0 || month == 0 || month > 12 || day == 0 || day > days_in_month(year, month) {
        return Err(TemporalError::InvalidDate);
    }
    if hour > 23 || minute > 59 || second > 59 {
        return Err(TemporalError::InvalidTime);
    }

    let microseconds = if bytes.len() == 19 {
        0
    } else {
        if bytes[19] != b'.' || bytes.len() == 20 {
            return Err(TemporalError::InvalidTimestamp);
        }
        let fraction = &bytes[20..];
        if !fraction.iter().all(u8::is_ascii_digit) {
            return Err(TemporalError::InvalidTimestamp);
        }
        let digits_to_keep = fraction.len().min(6);
        let value = parse_digits(fraction, 0, digits_to_keep)?;
        value * 10_u32.pow((6 - digits_to_keep) as u32)
    };

    Ok((year, month, day, hour, minute, second, microseconds))
}

fn parse_digits(bytes: &[u8], start: usize, end: usize) -> Result<u32, TemporalError> {
    if start >= end || end > bytes.len() || !bytes[start..end].iter().all(u8::is_ascii_digit) {
        return Err(TemporalError::InvalidTimestamp);
    }
    let mut value = 0_u32;
    for byte in &bytes[start..end] {
        value = value * 10 + u32::from(*byte - b'0');
    }
    Ok(value)
}

fn is_leap_year(year: i32) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap_year(year) => 29,
        2 => 28,
        _ => 0,
    }
}

// Proleptic Gregorian conversion, with day zero at 1970-01-01.
fn days_from_civil(year: i32, month: u32, day: u32) -> i64 {
    let adjustment = if month <= 2 { 1_i64 } else { 0_i64 };
    let year = i64::from(year) - adjustment;
    let era = if year >= 0 { year } else { year - 399 }.div_euclid(400);
    let year_of_era = year - era * 400;
    let adjusted_month = i64::from(month) + if month > 2 { -3 } else { 9 };
    let day_of_year = (153 * adjusted_month + 2) / 5 + i64::from(day) - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    era * 146_097 + day_of_era - 719_468
}

fn civil_from_days(days: i64) -> (i32, u32, u32) {
    let adjusted_days = days + 719_468;
    let era = if adjusted_days >= 0 {
        adjusted_days
    } else {
        adjusted_days - 146_096
    }
    .div_euclid(146_097);
    let day_of_era = adjusted_days - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let mut year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_prime = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_prime + 2) / 5 + 1;
    let month = month_prime + if month_prime < 10 { 3 } else { -9 };
    year += if month <= 2 { 1 } else { 0 };
    (year as i32, month as u32, day as u32)
}

fn ensure_supported_utc_year(unix_seconds: i64) -> Result<(), TemporalError> {
    let days = unix_seconds.div_euclid(SECONDS_PER_DAY);
    let (year, _, _) = civil_from_days(days);
    if !(1..=9999).contains(&year) {
        return Err(TemporalError::UtcOutOfRange);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{in_window, parse_rfc3339, to_rfc3339, TemporalError, TimeInterval};

    fn instant(text: &str) -> super::UtcInstant {
        parse_rfc3339(text).expect("test timestamp should be valid")
    }

    #[test]
    fn normalizes_offset_to_python_reference_precision() {
        let value = instant("2026-10-06T11:30:00+05:30");
        assert_eq!(to_rfc3339(value).unwrap(), "2026-10-06T06:00:00.000000Z");
    }

    #[test]
    fn preserves_microseconds_and_truncates_extra_fractional_digits() {
        let value = instant("2026-10-06T11:30:00.123456789+05:30");
        assert_eq!(to_rfc3339(value).unwrap(), "2026-10-06T06:00:00.123456Z");
    }

    #[test]
    fn accepts_utc_z_and_negative_offsets() {
        assert_eq!(
            to_rfc3339(instant("2026-01-01T00:00:00Z")).unwrap(),
            "2026-01-01T00:00:00.000000Z"
        );
        assert_eq!(
            to_rfc3339(instant("2026-01-01T00:00:00-02:30")).unwrap(),
            "2026-01-01T02:30:00.000000Z"
        );
    }

    #[test]
    fn rejects_naive_malformed_and_invalid_calendar_timestamps() {
        assert_eq!(
            parse_rfc3339("2026-10-06T11:30:00"),
            Err(TemporalError::MissingTimezone)
        );
        assert_eq!(
            parse_rfc3339("2025-02-29T11:30:00Z"),
            Err(TemporalError::InvalidDate)
        );
        assert_eq!(
            parse_rfc3339("2026-10-06T11:30:60Z"),
            Err(TemporalError::InvalidTime)
        );
        assert!(parse_rfc3339("2026-10-06T11:30:00+24:00").is_err());
        assert!(parse_rfc3339("not-a-time").is_err());
    }

    #[test]
    fn interval_is_half_open_and_rejects_empty_ranges() {
        let start = instant("2026-10-06T00:00:00Z");
        let middle = instant("2026-10-06T12:00:00Z");
        let end = instant("2026-10-07T00:00:00Z");
        let interval = TimeInterval::new(start, end).unwrap();

        assert!(interval.contains(start));
        assert!(interval.contains(middle));
        assert!(!interval.contains(end));
        assert_eq!(in_window(start, Some(start), Some(end)), Ok(true));
        assert_eq!(in_window(end, Some(start), Some(end)), Ok(false));
        assert_eq!(
            TimeInterval::new(end, start),
            Err(TemporalError::InvalidInterval)
        );
        assert_eq!(
            in_window(middle, Some(end), Some(start)),
            Err(TemporalError::InvalidInterval)
        );
    }

    #[test]
    fn overlapping_intervals_return_their_non_empty_intersection() {
        let first = TimeInterval::new(
            instant("2026-10-06T00:00:00Z"),
            instant("2026-10-07T00:00:00Z"),
        )
        .unwrap();
        let second = TimeInterval::new(
            instant("2026-10-06T12:00:00Z"),
            instant("2026-10-08T00:00:00Z"),
        )
        .unwrap();

        let overlap = first.intersection(second).unwrap();
        assert_eq!(
            to_rfc3339(overlap.start).unwrap(),
            "2026-10-06T12:00:00.000000Z"
        );
        assert_eq!(
            to_rfc3339(overlap.end).unwrap(),
            "2026-10-07T00:00:00.000000Z"
        );
        let touching = TimeInterval::new(
            instant("2026-10-07T00:00:00Z"),
            instant("2026-10-08T00:00:00Z"),
        )
        .unwrap();
        assert!(first.intersection(touching).is_none());
    }
}
