//! Expanded temporal relations and bitemporal query primitives.
//!
//! Intervals are non-empty and half-open through the existing `TimeInterval`
//! contract. These APIs extend, rather than replace, RFC 3339 normalization.

use crate::temporal::{TemporalError, TimeInterval, UtcInstant};

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

#[cfg(test)]
mod tests {
    use super::{relation, AllenRelation, BiTemporalInterval, Timeline};
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
}
