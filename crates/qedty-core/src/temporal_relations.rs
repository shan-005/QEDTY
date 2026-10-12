//! Expanded temporal relations and bitemporal query primitives.
//!
//! Intervals are non-empty and half-open through the existing `TimeInterval`
//! contract. These APIs extend, rather than replace, RFC 3339 normalization.

use crate::deterministic_id;
use crate::temporal::{TemporalError, TimeInterval, UtcInstant};
use serde_json::{json, Value};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AllenRelation {
    Before,
    Meets,
    Overlaps,
    Starts,
    During,
    Finishes,
    Equals,
    FinishedBy,
    Contains,
    StartedBy,
    OverlappedBy,
    MetBy,
    After,
}

impl AllenRelation {
    pub const ALL: [Self; 13] = [
        Self::Before,
        Self::Meets,
        Self::Overlaps,
        Self::Starts,
        Self::During,
        Self::Finishes,
        Self::Equals,
        Self::FinishedBy,
        Self::Contains,
        Self::StartedBy,
        Self::OverlappedBy,
        Self::MetBy,
        Self::After,
    ];

    pub const fn inverse(self) -> Self {
        match self {
            Self::Before => Self::After,
            Self::Meets => Self::MetBy,
            Self::Overlaps => Self::OverlappedBy,
            Self::Starts => Self::StartedBy,
            Self::During => Self::Contains,
            Self::Finishes => Self::FinishedBy,
            Self::Equals => Self::Equals,
            Self::FinishedBy => Self::Finishes,
            Self::Contains => Self::During,
            Self::StartedBy => Self::Starts,
            Self::OverlappedBy => Self::Overlaps,
            Self::MetBy => Self::Meets,
            Self::After => Self::Before,
        }
    }
}

/// Return the Allen interval relation of `first` relative to `second`.
pub fn relation(first: TimeInterval, second: TimeInterval) -> AllenRelation {
    let (a, b, c, d) = (first.start(), first.end(), second.start(), second.end());
    if b < c {
        return AllenRelation::Before;
    }
    if b == c {
        return AllenRelation::Meets;
    }
    if a < c && c < b && b < d {
        return AllenRelation::Overlaps;
    }
    if a == c && b < d {
        return AllenRelation::Starts;
    }
    if c < a && b < d {
        return AllenRelation::During;
    }
    if c < a && b == d {
        return AllenRelation::Finishes;
    }
    if a == c && b == d {
        return AllenRelation::Equals;
    }
    // The remaining cases are exactly the inverse relation in reverse order.
    relation(second, first).inverse()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BiTemporalInterval {
    pub valid_time: TimeInterval,
    pub transaction_time: TimeInterval,
}

impl BiTemporalInterval {
    pub fn new(
        valid_start: UtcInstant,
        valid_end: UtcInstant,
        transaction_start: UtcInstant,
        transaction_end: UtcInstant,
    ) -> Result<Self, TemporalError> {
        Ok(Self {
            valid_time: TimeInterval::new(valid_start, valid_end)?,
            transaction_time: TimeInterval::new(transaction_start, transaction_end)?,
        })
    }

    /// Whether both valid time and transaction/system time contain the instants.
    pub fn contains(self, valid_at: UtcInstant, known_at: UtcInstant) -> bool {
        self.valid_time.contains(valid_at) && self.transaction_time.contains(known_at)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TimelineEntry<T> {
    pub interval: TimeInterval,
    pub value: T,
}

/// A deterministic timeline ordered by start then end.
/// Equal intervals retain insertion order because `sort_by` is stable.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Timeline<T> {
    entries: Vec<TimelineEntry<T>>,
}

impl<T> Timeline<T> {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn insert(&mut self, interval: TimeInterval, value: T) {
        self.entries.push(TimelineEntry { interval, value });
        self.entries.sort_by(|left, right| {
            left.interval
                .start()
                .cmp(&right.interval.start())
                .then_with(|| left.interval.end().cmp(&right.interval.end()))
        });
    }

    pub fn entries(&self) -> &[TimelineEntry<T>] {
        &self.entries
    }

    pub fn overlaps(&self, query: TimeInterval) -> impl Iterator<Item = &TimelineEntry<T>> {
        self.entries
            .iter()
            .filter(move |entry| entry.interval.intersection(query).is_some())
    }

    pub fn active_at(&self, instant: UtcInstant) -> impl Iterator<Item = &TimelineEntry<T>> {
        self.entries
            .iter()
            .filter(move |entry| entry.interval.contains(instant))
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// Optional-ended half-open extent. A missing start means negative infinity;
/// a missing end means positive infinity. Finite extents must be non-empty.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OpenTimeExtent {
    pub start: Option<UtcInstant>,
    pub end: Option<UtcInstant>,
}

impl OpenTimeExtent {
    pub fn new(start: Option<UtcInstant>, end: Option<UtcInstant>) -> Result<Self, TemporalError> {
        if matches!((start, end), (Some(left), Some(right)) if right <= left) {
            return Err(TemporalError::InvalidInterval);
        }
        Ok(Self { start, end })
    }

    /// Whether an instant belongs to the canonical half-open extent [start, end).
    pub fn contains(self, instant: UtcInstant) -> bool {
        let after_start = match self.start {
            None => true,
            Some(start) => instant >= start,
        };
        let before_end = match self.end {
            None => true,
            Some(end) => instant < end,
        };
        after_start && before_end
    }

    /// Whether two half-open extents share at least one instant.
    /// Touching endpoints do not intersect: [a, b) and [b, c) are disjoint.
    pub fn intersects(self, other: Self) -> bool {
        let self_before_other_end = match (self.start, other.end) {
            (Some(start), Some(end)) => start < end,
            _ => true,
        };
        let other_before_self_end = match (other.start, self.end) {
            (Some(start), Some(end)) => start < end,
            _ => true,
        };
        self_before_other_end && other_before_self_end
    }
}

/// Bitemporal membership across valid time and transaction/knowledge time.
/// Each coordinate uses the same half-open, optionally unbounded extent rules.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BitemporalExtent {
    pub valid_time: OpenTimeExtent,
    pub transaction_time: OpenTimeExtent,
}

impl BitemporalExtent {
    pub fn new(
        valid_start: Option<UtcInstant>,
        valid_end: Option<UtcInstant>,
        transaction_start: Option<UtcInstant>,
        transaction_end: Option<UtcInstant>,
    ) -> Result<Self, TemporalError> {
        Ok(Self {
            valid_time: OpenTimeExtent::new(valid_start, valid_end)?,
            transaction_time: OpenTimeExtent::new(transaction_start, transaction_end)?,
        })
    }

    pub fn contains(self, valid_at: UtcInstant, transaction_at: UtcInstant) -> bool {
        self.valid_time.contains(valid_at) && self.transaction_time.contains(transaction_at)
    }
}

/// One event point in the value timeline. Sequence breaks equal-instant ties;
/// stable insertion order is retained if both instant and sequence are equal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PointTimelineEntry<T> {
    pub at: UtcInstant,
    pub value: T,
    pub sequence: i64,
}

/// Point/event timeline matching QEDTY's Python Timeline query semantics.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct PointTimeline<T> {
    entries: Vec<PointTimelineEntry<T>>,
}

impl<T> PointTimeline<T> {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn put(&mut self, at: UtcInstant, value: T, sequence: i64) {
        self.entries.push(PointTimelineEntry {
            at,
            value,
            sequence,
        });
        self.entries.sort_by(|left, right| {
            left.at
                .cmp(&right.at)
                .then_with(|| left.sequence.cmp(&right.sequence))
        });
    }

    pub fn at_or_before(&self, at: UtcInstant) -> Option<&PointTimelineEntry<T>> {
        self.entries.iter().rev().find(|point| point.at <= at)
    }

    pub fn at_or_after(&self, at: UtcInstant) -> Option<&PointTimelineEntry<T>> {
        self.entries.iter().find(|point| point.at >= at)
    }

    pub fn between(
        &self,
        start: UtcInstant,
        end: UtcInstant,
        include_end: bool,
    ) -> impl Iterator<Item = &PointTimelineEntry<T>> {
        self.entries.iter().filter(move |point| {
            point.at >= start
                && if include_end {
                    point.at <= end
                } else {
                    point.at < end
                }
        })
    }

    pub fn latest(&self) -> Option<&PointTimelineEntry<T>> {
        self.entries.last()
    }

    pub fn entries(&self) -> &[PointTimelineEntry<T>] {
        &self.entries
    }

    pub fn values(&self) -> impl Iterator<Item = &T> {
        self.entries.iter().map(|point| &point.value)
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// One value stored in QEDTY's temporal index.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TemporalIndexEntry<T> {
    pub key: String,
    pub extent: OpenTimeExtent,
    pub value: T,
}

/// Stable failures from temporal-index key operations.
#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum TemporalIndexError {
    #[error("temporal index collision: {0}")]
    Collision(String),
    #[error("temporal index key not found: {0}")]
    MissingKey(String),
}

/// In-memory reference contract for keyed temporal intervals.
///
/// Query result order for `at` and `overlapping` follows insertion order.
/// `all` sorts by start (unbounded first), then lexical key. Re-adding an
/// identical key/extent/value is idempotent; reusing the key for other data
/// is a collision.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TemporalIndex<T> {
    entries: Vec<TemporalIndexEntry<T>>,
}

impl<T: Clone + PartialEq> TemporalIndex<T> {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn add(
        &mut self,
        key: impl Into<String>,
        extent: OpenTimeExtent,
        value: T,
    ) -> Result<(), TemporalIndexError> {
        let key = key.into();
        if let Some(existing) = self.entries.iter().find(|entry| entry.key == key) {
            if existing.extent == extent && existing.value == value {
                return Ok(());
            }
            return Err(TemporalIndexError::Collision(key));
        }
        self.entries.push(TemporalIndexEntry { key, extent, value });
        Ok(())
    }

    pub fn get(&self, key: &str) -> Result<&TemporalIndexEntry<T>, TemporalIndexError> {
        self.entries
            .iter()
            .find(|entry| entry.key == key)
            .ok_or_else(|| TemporalIndexError::MissingKey(key.to_owned()))
    }

    pub fn remove(&mut self, key: &str) -> Result<TemporalIndexEntry<T>, TemporalIndexError> {
        let index = self
            .entries
            .iter()
            .position(|entry| entry.key == key)
            .ok_or_else(|| TemporalIndexError::MissingKey(key.to_owned()))?;
        Ok(self.entries.remove(index))
    }

    pub fn overlapping(&self, query: OpenTimeExtent) -> Vec<T> {
        self.entries
            .iter()
            .filter(|entry| entry.extent.intersects(query))
            .map(|entry| entry.value.clone())
            .collect()
    }

    pub fn at(&self, instant: UtcInstant) -> Vec<T> {
        self.entries
            .iter()
            .filter(|entry| entry.extent.contains(instant))
            .map(|entry| entry.value.clone())
            .collect()
    }

    pub fn all(&self) -> Vec<TemporalIndexEntry<T>> {
        let mut entries = self.entries.clone();
        entries.sort_by(|left, right| {
            left.extent
                .start
                .cmp(&right.extent.start)
                .then_with(|| left.key.cmp(&right.key))
        });
        entries
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn clear(&mut self) {
        self.entries.clear();
    }
}


/// Immutable, bitemporal record matching QEDTY's Python TemporalVersion model.
///
/// The identifier preimage contains the record key, both canonical extents, and
/// the value. Supersession links and metadata are part of the stored version
/// but intentionally do not participate in its identity.
#[derive(Debug, Clone, PartialEq)]
pub struct TemporalVersionRecord {
    pub version_id: String,
    pub record_key: String,
    pub value: Value,
    pub valid_time: OpenTimeExtent,
    pub transaction_time: OpenTimeExtent,
    pub supersedes: Vec<String>,
    pub metadata: Value,
}

fn python_timestamp(value: UtcInstant) -> Result<String, String> {
    let formatted = crate::temporal::to_rfc3339(value).map_err(|error| error.to_string())?;
    if let Some(seconds) = formatted.strip_suffix(".000000Z") {
        Ok(format!("{seconds}Z"))
    } else {
        Ok(formatted)
    }
}

fn temporal_version_extent_value(extent: OpenTimeExtent) -> Result<Value, String> {
    let start = match extent.start {
        Some(value) => Value::String(python_timestamp(value)?),
        None => Value::Null,
    };
    let end = match extent.end {
        Some(value) => Value::String(python_timestamp(value)?),
        None => Value::Null,
    };
    Ok(json!({
        "start": start,
        "end": end,
        "start_inclusive": true,
        "end_inclusive": false,
    }))
}

impl TemporalVersionRecord {
    pub fn create(
        record_key: String,
        value: Value,
        valid_time: OpenTimeExtent,
        transaction_time: OpenTimeExtent,
        supersedes: Vec<String>,
        metadata: Value,
    ) -> Result<Self, String> {
        if record_key.is_empty() || record_key.chars().count() > 512 {
            return Err("record_key must contain between 1 and 512 characters".to_owned());
        }
        let valid_json = temporal_version_extent_value(valid_time)?;
        let transaction_json = temporal_version_extent_value(transaction_time)?;
        let parts = [valid_json, transaction_json, value.clone()];
        let version_id = deterministic_id("temporal-version", &record_key, &parts, 32)
            .map_err(|error| error.to_string())?;
        Ok(Self {
            version_id,
            record_key,
            value,
            valid_time,
            transaction_time,
            supersedes,
            metadata,
        })
    }

    pub fn from_payload(
        version_id: String,
        record_key: String,
        value: Value,
        valid_time: OpenTimeExtent,
        transaction_time: OpenTimeExtent,
        supersedes: Vec<String>,
        metadata: Value,
    ) -> Result<Self, String> {
        if version_id.is_empty() || version_id.chars().count() > 256 {
            return Err("version_id must contain between 1 and 256 characters".to_owned());
        }
        let version = Self::create(
            record_key,
            value,
            valid_time,
            transaction_time,
            supersedes,
            metadata,
        )?;
        if version.version_id != version_id {
            return Err("version_id does not match canonical version identity".to_owned());
        }
        Ok(version)
    }

    pub fn to_json(&self) -> Result<Value, String> {
        Ok(json!({
            "version_id": self.version_id,
            "record_key": self.record_key,
            "value": self.value,
            "valid_time": temporal_version_extent_value(self.valid_time)?,
            "transaction_time": temporal_version_extent_value(self.transaction_time)?,
            "supersedes": self.supersedes,
            "metadata": self.metadata,
        }))
    }

    fn history_order_key(&self) -> (Option<UtcInstant>, &str) {
        (self.transaction_time.start, self.version_id.as_str())
    }
}

/// Stable history-index failures, matching the Python reference operations.
#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum TemporalHistoryError {
    #[error("version collision: {0}")]
    Collision(String),
    #[error("temporal version not found: {0}")]
    MissingVersion(String),
}

/// Append-only bitemporal version history with deterministic query selection.
#[derive(Debug, Clone, Default)]
pub struct TemporalHistory {
    versions: std::collections::BTreeMap<String, TemporalVersionRecord>,
}

impl TemporalHistory {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add(&mut self, version: TemporalVersionRecord) -> Result<(), TemporalHistoryError> {
        if let Some(previous) = self.versions.get(&version.version_id) {
            if previous != &version {
                return Err(TemporalHistoryError::Collision(version.version_id));
            }
            return Ok(());
        }
        self.versions.insert(version.version_id.clone(), version);
        Ok(())
    }

    pub fn get(&self, version_id: &str) -> Result<&TemporalVersionRecord, TemporalHistoryError> {
        self.versions
            .get(version_id)
            .ok_or_else(|| TemporalHistoryError::MissingVersion(version_id.to_owned()))
    }

    pub fn all(&self) -> Vec<TemporalVersionRecord> {
        self.versions.values().cloned().collect()
    }

    pub fn as_of(
        &self,
        valid_at: UtcInstant,
        transaction_at: UtcInstant,
    ) -> Vec<TemporalVersionRecord> {
        let mut chosen: std::collections::BTreeMap<String, TemporalVersionRecord> =
            std::collections::BTreeMap::new();
        for version in self.versions.values().filter(|version| {
            version.valid_time.contains(valid_at) && version.transaction_time.contains(transaction_at)
        }) {
            let replace = chosen
                .get(&version.record_key)
                .map(|current| version.history_order_key() > current.history_order_key())
                .unwrap_or(true);
            if replace {
                chosen.insert(version.record_key.clone(), version.clone());
            }
        }
        chosen.into_values().collect()
    }

    /// Latest version known at the transaction instant, regardless of valid time.
    pub fn latest_known(
        &self,
        record_key: &str,
        transaction_at: UtcInstant,
    ) -> Option<TemporalVersionRecord> {
        self.versions
            .values()
            .filter(|version| {
                version.record_key == record_key
                    && version.transaction_time.contains(transaction_at)
            })
            .max_by(|left, right| left.history_order_key().cmp(&right.history_order_key()))
            .cloned()
    }

    pub fn len(&self) -> usize {
        self.versions.len()
    }

    pub fn is_empty(&self) -> bool {
        self.versions.is_empty()
    }
}


#[cfg(test)]
mod tests {
    use super::{
        relation, AllenRelation, BiTemporalInterval, OpenTimeExtent, TemporalIndex,
        TemporalIndexError, Timeline,
    };
    use crate::temporal::{parse_rfc3339, TimeInterval};

    fn instant(day: u32) -> crate::temporal::UtcInstant {
        parse_rfc3339(&format!("2026-10-{day:02}T00:00:00Z")).unwrap()
    }
    fn interval(start: u32, end: u32) -> TimeInterval {
        TimeInterval::new(instant(start), instant(end)).unwrap()
    }

    #[test]
    fn classifies_allen_relations_and_inverses() {
        assert_eq!(
            relation(interval(1, 2), interval(3, 4)),
            AllenRelation::Before
        );
        assert_eq!(
            relation(interval(1, 2), interval(2, 4)),
            AllenRelation::Meets
        );
        assert_eq!(
            relation(interval(1, 4), interval(2, 5)),
            AllenRelation::Overlaps
        );
        assert_eq!(
            relation(interval(1, 3), interval(1, 4)),
            AllenRelation::Starts
        );
        assert_eq!(
            relation(interval(2, 3), interval(1, 4)),
            AllenRelation::During
        );
        assert_eq!(
            relation(interval(2, 4), interval(1, 4)),
            AllenRelation::Finishes
        );
        assert_eq!(
            relation(interval(1, 4), interval(1, 4)),
            AllenRelation::Equals
        );
        assert_eq!(
            relation(interval(1, 5), interval(2, 4)),
            AllenRelation::Contains
        );
        assert_eq!(
            relation(interval(1, 5), interval(2, 5)),
            AllenRelation::FinishedBy
        );
        assert_eq!(
            relation(interval(1, 4), interval(1, 3)),
            AllenRelation::StartedBy
        );
        assert_eq!(
            relation(interval(2, 5), interval(1, 4)),
            AllenRelation::OverlappedBy
        );
        assert_eq!(
            relation(interval(2, 4), interval(1, 2)),
            AllenRelation::MetBy
        );
        assert_eq!(
            relation(interval(3, 4), interval(1, 2)),
            AllenRelation::After
        );
        for relation in AllenRelation::ALL {
            assert_eq!(relation.inverse().inverse(), relation);
        }
    }

    #[test]
    fn generated_interval_pairs_obey_relation_inverse_law() {
        let intervals: Vec<_> = (1..10)
            .flat_map(|start| ((start + 1)..=10).map(move |end| interval(start, end)))
            .collect();
        for first in &intervals {
            for second in &intervals {
                let forward = relation(*first, *second);
                let reverse = relation(*second, *first);
                assert_eq!(forward.inverse(), reverse);
            }
        }
    }

    #[test]
    fn bitemporal_membership_checks_both_clocks() {
        let item =
            BiTemporalInterval::new(instant(1), instant(10), instant(3), instant(8)).unwrap();
        assert!(item.contains(instant(5), instant(5)));
        assert!(!item.contains(instant(5), instant(8)));
        assert!(!item.contains(instant(10), instant(5)));
    }

    #[test]
    fn bitemporal_open_bounds_are_half_open_on_both_clocks() {
        use super::BitemporalExtent;

        let valid_start = instant(1);
        let transaction_end = instant(8);
        let extent =
            BitemporalExtent::new(Some(valid_start), None, None, Some(transaction_end)).unwrap();
        assert!(extent.contains(instant(1), instant(5)));
        assert!(!extent.contains(instant(5), transaction_end));
    }

    #[test]
    fn point_timeline_orders_by_instant_then_sequence_stably() {
        use super::PointTimeline;

        let mut timeline = PointTimeline::new();
        timeline.put(instant(3), "late", 0);
        timeline.put(instant(1), "seq-3-first", 3);
        timeline.put(instant(1), "seq-minus-one", -1);
        timeline.put(instant(1), "seq-3-second", 3);

        let values: Vec<_> = timeline.values().copied().collect();
        assert_eq!(
            values,
            vec!["seq-minus-one", "seq-3-first", "seq-3-second", "late"]
        );
        assert_eq!(
            timeline.at_or_before(instant(1)).map(|point| point.value),
            Some("seq-3-second")
        );
        assert_eq!(
            timeline.at_or_after(instant(2)).map(|point| point.value),
            Some("late")
        );
        assert_eq!(timeline.between(instant(1), instant(3), false).count(), 3);
        assert_eq!(timeline.between(instant(1), instant(3), true).count(), 4);
    }

    #[test]
    fn timeline_is_sorted_and_uses_half_open_overlap() {
        let mut timeline = Timeline::new();
        timeline.insert(interval(5, 8), "late");
        timeline.insert(interval(1, 4), "early");
        timeline.insert(interval(4, 5), "touching");
        assert_eq!(timeline.entries()[0].value, "early");
        assert_eq!(
            timeline
                .active_at(instant(4))
                .map(|e| e.value)
                .collect::<Vec<_>>(),
            vec!["touching"]
        );
        assert_eq!(timeline.overlaps(interval(2, 5)).count(), 2);
    }
    #[test]
    fn temporal_index_queries_preserve_insertion_order_and_half_open_bounds() {
        let mut index = TemporalIndex::new();
        index
            .add(
                "before",
                OpenTimeExtent::new(Some(instant(1)), Some(instant(3))).unwrap(),
                "before",
            )
            .unwrap();
        index
            .add(
                "all-time",
                OpenTimeExtent::new(None, None).unwrap(),
                "all-time",
            )
            .unwrap();
        index
            .add(
                "starts",
                OpenTimeExtent::new(Some(instant(3)), Some(instant(5))).unwrap(),
                "starts",
            )
            .unwrap();

        assert_eq!(index.at(instant(3)), vec!["all-time", "starts"]);
        assert_eq!(
            index.overlapping(OpenTimeExtent::new(Some(instant(3)), Some(instant(4))).unwrap()),
            vec!["all-time", "starts"]
        );
        let all = index.all();
        assert_eq!(
            all.iter()
                .map(|entry| entry.key.as_str())
                .collect::<Vec<_>>(),
            vec!["all-time", "before", "starts"]
        );
    }

    #[test]
    fn temporal_index_duplicate_add_is_idempotent_but_conflicts_are_rejected() {
        let mut index = TemporalIndex::new();
        let extent = OpenTimeExtent::new(Some(instant(1)), Some(instant(3))).unwrap();
        index.add("key", extent, "value").unwrap();
        index.add("key", extent, "value").unwrap();
        assert_eq!(index.len(), 1);
        assert_eq!(
            index.add(
                "key",
                OpenTimeExtent::new(Some(instant(1)), Some(instant(4))).unwrap(),
                "value"
            ),
            Err(TemporalIndexError::Collision("key".to_owned()))
        );
        assert_eq!(
            index.add("key", extent, "different"),
            Err(TemporalIndexError::Collision("key".to_owned()))
        );
        assert_eq!(index.len(), 1);
    }

    #[test]
    fn temporal_index_get_remove_and_clear_have_explicit_missing_key_errors() {
        let mut index = TemporalIndex::new();
        let extent = OpenTimeExtent::new(None, Some(instant(4))).unwrap();
        index.add("key", extent, "value").unwrap();
        assert_eq!(index.get("key").unwrap().value, "value");
        assert_eq!(index.remove("key").unwrap().key, "key");
        assert_eq!(
            index.get("missing").unwrap_err(),
            TemporalIndexError::MissingKey("missing".to_owned())
        );
        assert_eq!(
            index.remove("missing"),
            Err(TemporalIndexError::MissingKey("missing".to_owned()))
        );
        index.add("other", extent, "v").unwrap();
        index.clear();
        assert!(index.is_empty());
    }
    #[test]
    fn temporal_version_identity_uses_record_key_extents_and_value_only() {
        use super::{OpenTimeExtent, TemporalVersionRecord};
        use serde_json::json;

        let valid = OpenTimeExtent::new(Some(instant(1)), None).unwrap();
        let transaction = OpenTimeExtent::new(Some(instant(2)), Some(instant(4))).unwrap();
        let first = TemporalVersionRecord::create(
            "asset:1".to_owned(),
            json!({"capacity": 100}),
            valid,
            transaction,
            vec![],
            json!({}),
        )
        .unwrap();
        assert_eq!(
            first.version_id,
            "temporal-version:c6c55f7f243be56bf84147d3ca0a9837"
        );
        let decorated = TemporalVersionRecord::create(
            "asset:1".to_owned(),
            json!({"capacity": 100}),
            valid,
            transaction,
            vec!["older".to_owned()],
            json!({"source": "audit"}),
        )
        .unwrap();
        assert_eq!(first.version_id, decorated.version_id);
        assert_ne!(first, decorated);
    }

    #[test]
    fn temporal_history_as_of_uses_both_clocks_and_stable_record_order() {
        use super::{OpenTimeExtent, TemporalHistory, TemporalVersionRecord};
        use serde_json::json;

        let valid = OpenTimeExtent::new(Some(instant(1)), None).unwrap();
        let early_tx = OpenTimeExtent::new(Some(instant(2)), Some(instant(4))).unwrap();
        let late_tx = OpenTimeExtent::new(Some(instant(4)), None).unwrap();
        let mut history = TemporalHistory::new();
        for version in [
            TemporalVersionRecord::create(
                "z-record".to_owned(),
                json!({"v": 1}),
                valid,
                early_tx,
                vec![],
                json!({}),
            )
            .unwrap(),
            TemporalVersionRecord::create(
                "a-record".to_owned(),
                json!({"v": 2}),
                valid,
                late_tx,
                vec![],
                json!({}),
            )
            .unwrap(),
        ] {
            history.add(version).unwrap();
        }

        let selected = history.as_of(instant(3), instant(3));
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0].record_key, "z-record");
        assert_eq!(history.as_of(instant(1), instant(4)).len(), 1);
        assert_eq!(history.as_of(instant(3), instant(4)).len(), 1);
    }

    #[test]
    fn temporal_history_latest_known_ignores_valid_time_and_prefers_latest_start_then_id() {
        use super::{OpenTimeExtent, TemporalHistory, TemporalVersionRecord};
        use serde_json::json;

        let tx = OpenTimeExtent::new(Some(instant(2)), None).unwrap();
        let future_valid = OpenTimeExtent::new(Some(instant(8)), None).unwrap();
        let mut history = TemporalHistory::new();
        let version = TemporalVersionRecord::create(
            "asset".to_owned(),
            json!({"v": 7}),
            future_valid,
            tx,
            vec![],
            json!({}),
        )
        .unwrap();
        history.add(version.clone()).unwrap();
        assert_eq!(
            history.latest_known("asset", instant(3)).unwrap().version_id,
            version.version_id
        );
        assert!(history.latest_known("asset", instant(2)).is_some());
        assert!(history.latest_known("missing", instant(3)).is_none());
    }

    #[test]
    fn temporal_history_duplicate_add_is_idempotent_and_conflicts_are_rejected() {
        use super::{OpenTimeExtent, TemporalHistory, TemporalHistoryError, TemporalVersionRecord};
        use serde_json::json;

        let valid = OpenTimeExtent::new(Some(instant(1)), None).unwrap();
        let transaction = OpenTimeExtent::new(Some(instant(2)), None).unwrap();
        let version = TemporalVersionRecord::create(
            "asset".to_owned(),
            json!({"v": 1}),
            valid,
            transaction,
            vec![],
            json!({}),
        )
        .unwrap();
        let mut history = TemporalHistory::new();
        history.add(version.clone()).unwrap();
        history.add(version.clone()).unwrap();
        let mut conflicting = version.clone();
        conflicting.metadata = json!({"reviewed": true});
        assert_eq!(
            history.add(conflicting),
            Err(TemporalHistoryError::Collision(version.version_id.clone()))
        );
        assert_eq!(history.len(), 1);
        assert_eq!(history.all()[0].version_id, version.version_id);
        assert_eq!(
            history.get("absent"),
            Err(TemporalHistoryError::MissingVersion("absent".to_owned())).as_ref()
        );
    }

}
