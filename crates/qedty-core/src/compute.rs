//! Deterministic numeric kernels for continuity, uncertainty, propagation and selection.
//!
//! These pure kernels define input/error boundaries and deterministic ordering;
//! domain adapters still need Python differential fixtures before being treated as
//! drop-in replacements for every QEDTY domain service.

use std::collections::BTreeSet;
use thiserror::Error;

#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum ComputeError {
    #[error("input contains a non-finite value")]
    NonFinite,
    #[error("weights must be non-negative and their sum must be positive")]
    InvalidWeights,
    #[error("interval lower bound must not exceed upper bound")]
    InvalidInterval,
    #[error(
        "capacity, item count, resource budget, demand, damping or iteration count is invalid"
    )]
    InvalidParameter,
    #[error("propagation matrix contains an invalid node index or weight")]
    InvalidPropagationEdge,
    #[error("item identifiers must be non-blank, unique, and at most 128 bytes; weights must be positive and values non-negative")]
    InvalidItem,
}

fn require_finite(value: f64) -> Result<(), ComputeError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(ComputeError::NonFinite)
    }
}

pub fn weighted_mean(values: &[f64], weights: &[f64]) -> Result<f64, ComputeError> {
    if values.len() != weights.len() || values.is_empty() {
        return Err(ComputeError::InvalidWeights);
    }

    let mut max_abs_value: f64 = 0.0;
    let mut max_weight: f64 = 0.0;
    for (&value, &weight) in values.iter().zip(weights) {
        require_finite(value)?;
        require_finite(weight)?;
        if weight < 0.0 {
            return Err(ComputeError::InvalidWeights);
        }
        max_abs_value = max_abs_value.max(value.abs());
        max_weight = max_weight.max(weight);
    }
    if max_weight == 0.0 {
        return Err(ComputeError::InvalidWeights);
    }
    if max_abs_value == 0.0 {
        return Ok(0.0);
    }

    // Normalize values and weights before summation to avoid overflowing
    // value * weight when the mathematically valid mean is representable.
    let mut weighted_sum = 0.0;
    let mut total_weight = 0.0;
    for (&value, &weight) in values.iter().zip(weights) {
        let normalized_weight = weight / max_weight;
        weighted_sum += (value / max_abs_value) * normalized_weight;
        total_weight += normalized_weight;
    }
    if !weighted_sum.is_finite() || !total_weight.is_finite() || total_weight <= 0.0 {
        return Err(ComputeError::NonFinite);
    }

    let normalized_mean = (weighted_sum / total_weight).clamp(-1.0, 1.0);
    let result = max_abs_value * normalized_mean;
    if result.is_finite() {
        Ok(result)
    } else {
        Err(ComputeError::NonFinite)
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct IntervalEstimate {
    lower: f64,
    upper: f64,
}

impl IntervalEstimate {
    pub const fn lower(self) -> f64 {
        self.lower
    }

    pub const fn upper(self) -> f64 {
        self.upper
    }

    pub fn new(lower: f64, upper: f64) -> Result<Self, ComputeError> {
        require_finite(lower)?;
        require_finite(upper)?;
        if lower > upper {
            return Err(ComputeError::InvalidInterval);
        }
        Ok(Self { lower, upper })
    }

    pub fn midpoint(self) -> f64 {
        if self.lower < 0.0 && self.upper > 0.0 {
            (self.lower + self.upper) / 2.0
        } else {
            self.lower + (self.upper - self.lower) / 2.0
        }
    }
    /// Raw IEEE-754 width; can be infinite if subtraction overflows.
    pub fn width(self) -> f64 {
        self.upper - self.lower
    }

    /// Return an error when the interval width is not representable as a finite f64.
    pub fn checked_width(self) -> Result<f64, ComputeError> {
        let width = self.width();
        if width.is_finite() {
            Ok(width)
        } else {
            Err(ComputeError::NonFinite)
        }
    }

    pub fn intersect(self, other: Self) -> Option<Self> {
        let lower = self.lower.max(other.lower);
        let upper = self.upper.min(other.upper);
        (lower <= upper).then_some(Self { lower, upper })
    }

    pub fn checked_add(self, other: Self) -> Result<Self, ComputeError> {
        Self::new(self.lower + other.lower, self.upper + other.upper)
    }

    pub fn checked_subtract(self, other: Self) -> Result<Self, ComputeError> {
        Self::new(self.lower - other.upper, self.upper - other.lower)
    }
}

/// Availability divided by demand, clamped to [0, 1]. Zero demand is fully covered.
pub fn continuity_score(available_capacity: f64, demand: f64) -> Result<f64, ComputeError> {
    require_finite(available_capacity)?;
    require_finite(demand)?;
    if available_capacity < 0.0 || demand < 0.0 {
        return Err(ComputeError::InvalidParameter);
    }
    if demand == 0.0 {
        return Ok(1.0);
    }
    Ok((available_capacity / demand).clamp(0.0, 1.0))
}

/// Deterministic synchronous propagation over weighted adjacency lists.
/// Each `(destination, weight)` adds `current[source] * weight` to the next step.
pub fn propagate_linear(
    initial: &[f64],
    edges: &[Vec<(usize, f64)>],
    damping: f64,
    iterations: usize,
) -> Result<Vec<f64>, ComputeError> {
    if initial.is_empty()
        || initial.len() != edges.len()
        || iterations == 0
        || !damping.is_finite()
        || !(0.0..=1.0).contains(&damping)
    {
        return Err(ComputeError::InvalidParameter);
    }
    for value in initial {
        require_finite(*value)?;
    }
    for adjacency in edges {
        for (destination, weight) in adjacency {
            if *destination >= initial.len() || !weight.is_finite() || *weight < 0.0 {
                return Err(ComputeError::InvalidPropagationEdge);
            }
        }
    }
    let mut current = initial.to_vec();
    for _ in 0..iterations {
        let mut next = vec![0.0; initial.len()];
        for (source, adjacency) in edges.iter().enumerate() {
            for &(destination, weight) in adjacency {
                next[destination] += current[source] * damping * weight;
            }
        }
        for (index, base) in initial.iter().enumerate() {
            next[index] += base * (1.0 - damping);
        }
        if next.iter().any(|value| !value.is_finite()) {
            return Err(ComputeError::NonFinite);
        }
        current = next;
    }
    Ok(current)
}

#[derive(Debug, Clone, PartialEq)]
pub struct KnapsackItem {
    pub id: String,
    pub weight: usize,
    pub value: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct KnapsackResult {
    pub selected_ids: Vec<String>,
    pub total_weight: usize,
    pub total_value: f64,
}

#[derive(Debug, Clone)]
struct Choice {
    ids: Vec<String>,
    weight: usize,
    value: f64,
}

fn better(candidate: &Choice, current: &Choice) -> bool {
    candidate.value > current.value
        || (candidate.value == current.value && candidate.ids < current.ids)
}

/// Exact 0/1 knapsack DP. IDs are unique, sorted, and used to break value ties.
/// Capacity, item count, identifier size, and the capacity/item product are bounded
/// because each DP state stores its selected identifiers.
pub const MAX_KNAPSACK_CAPACITY: usize = 1_000_000;
pub const MAX_KNAPSACK_ITEMS: usize = 128;
pub const MAX_KNAPSACK_ID_BYTES: usize = 128;
pub const MAX_KNAPSACK_STATE_ID_ENTRIES: usize = 200_000;

pub fn knapsack(items: &[KnapsackItem], capacity: usize) -> Result<KnapsackResult, ComputeError> {
    // Each DP slot stores a vector of selected IDs. Capacity alone is not a
    // sufficient memory bound when many items can be selected.
    let state_id_budget = capacity
        .saturating_add(1)
        .saturating_mul(items.len().max(1));
    if capacity > MAX_KNAPSACK_CAPACITY
        || items.len() > MAX_KNAPSACK_ITEMS
        || state_id_budget > MAX_KNAPSACK_STATE_ID_ENTRIES
    {
        return Err(ComputeError::InvalidParameter);
    }
    let mut seen = BTreeSet::new();
    let mut ordered = items.to_vec();
    for item in &ordered {
        if item.id.trim().is_empty()
            || item.id.len() > MAX_KNAPSACK_ID_BYTES
            || item.weight == 0
            || !item.value.is_finite()
            || item.value < 0.0
            || !seen.insert(item.id.clone())
        {
            return Err(ComputeError::InvalidItem);
        }
    }
    ordered.sort_by(|a, b| a.id.cmp(&b.id));
    let empty = Choice {
        ids: Vec::new(),
        weight: 0,
        value: 0.0,
    };
    let mut dp = vec![empty.clone(); capacity.saturating_add(1)];
    for item in ordered {
        if item.weight > capacity {
            continue;
        }
        for current_capacity in (item.weight..=capacity).rev() {
            let previous = dp[current_capacity - item.weight].clone();
            let mut candidate = previous;
            candidate.ids.push(item.id.clone());
            candidate.ids.sort();
            candidate.weight += item.weight;
            candidate.value += item.value;
            if !candidate.value.is_finite() {
                return Err(ComputeError::NonFinite);
            }
            if better(&candidate, &dp[current_capacity]) {
                dp[current_capacity] = candidate;
            }
        }
    }
    let best = dp
        .into_iter()
        .reduce(|a, b| if better(&b, &a) { b } else { a })
        .unwrap_or(empty);
    Ok(KnapsackResult {
        selected_ids: best.ids,
        total_weight: best.weight,
        total_value: best.value,
    })
}

#[cfg(test)]
mod tests {
    use super::{
        continuity_score, knapsack, propagate_linear, weighted_mean, ComputeError,
        IntervalEstimate, KnapsackItem,
    };

    #[test]
    fn uncertainty_intervals_preserve_bounds_and_conservative_arithmetic() {
        let first = IntervalEstimate::new(80.0, 120.0).unwrap();
        let second = IntervalEstimate::new(5.0, 10.0).unwrap();
        assert_eq!(
            first.checked_add(second).unwrap(),
            IntervalEstimate {
                lower: 85.0,
                upper: 130.0
            }
        );
        assert_eq!(
            first.checked_subtract(second).unwrap(),
            IntervalEstimate {
                lower: 70.0,
                upper: 115.0
            }
        );
        let extreme = IntervalEstimate::new(-f64::MAX, f64::MAX).unwrap();
        assert!(extreme.midpoint().is_finite());
        assert_eq!(extreme.checked_width(), Err(ComputeError::NonFinite));
        assert_eq!(
            IntervalEstimate::new(2.0, 5.0).unwrap().checked_width(),
            Ok(3.0)
        );
        assert_eq!(
            first.intersect(IntervalEstimate::new(100.0, 140.0).unwrap()),
            Some(IntervalEstimate {
                lower: 100.0,
                upper: 120.0
            })
        );
        assert_eq!(
            IntervalEstimate::new(2.0, 1.0),
            Err(ComputeError::InvalidInterval)
        );
    }

    #[test]
    fn weighted_mean_and_continuity_score_validate_domains() {
        assert!((weighted_mean(&[2.0, 4.0], &[1.0, 3.0]).unwrap() - 3.5).abs() < 1e-12);
        assert_eq!(
            weighted_mean(&[f64::MAX, f64::MAX], &[f64::MAX, f64::MAX]).unwrap(),
            f64::MAX
        );
        assert_eq!(
            weighted_mean(&[f64::MAX, -f64::MAX], &[1.0, 1.0]).unwrap(),
            0.0
        );
        assert_eq!(continuity_score(50.0, 100.0).unwrap(), 0.5);
        assert_eq!(continuity_score(120.0, 100.0).unwrap(), 1.0);
        assert_eq!(continuity_score(0.0, 0.0).unwrap(), 1.0);
        assert!(weighted_mean(&[2.0], &[0.0]).is_err());
    }

    #[test]
    fn propagation_is_repeatable_and_bounded_by_explicit_iteration_count() {
        let result = propagate_linear(&[1.0, 0.0], &[vec![(1, 1.0)], vec![]], 0.5, 1).unwrap();
        assert_eq!(result, vec![0.5, 0.5]);

        let zero_damping =
            propagate_linear(&[f64::MAX, 0.0], &[vec![(1, f64::MAX)], vec![]], 0.0, 1).unwrap();
        assert_eq!(zero_damping, vec![f64::MAX, 0.0]);

        assert!(propagate_linear(&[1.0], &[vec![(1, 1.0)]], 0.5, 2).is_err());
    }

    #[test]
    fn knapsack_rejects_oversized_resource_budgets_before_allocation() {
        let item = KnapsackItem {
            id: "x".into(),
            weight: 1,
            value: 1.0,
        };
        assert_eq!(
            knapsack(std::slice::from_ref(&item), super::MAX_KNAPSACK_CAPACITY),
            Err(ComputeError::InvalidParameter)
        );

        let oversized_id = KnapsackItem {
            id: "x".repeat(super::MAX_KNAPSACK_ID_BYTES + 1),
            weight: 1,
            value: 1.0,
        };
        assert_eq!(knapsack(&[oversized_id], 1), Err(ComputeError::InvalidItem));
    }

    #[test]
    fn knapsack_uses_stable_ids_to_break_ties() {
        let items = [
            KnapsackItem {
                id: "b".into(),
                weight: 2,
                value: 3.0,
            },
            KnapsackItem {
                id: "a".into(),
                weight: 2,
                value: 3.0,
            },
            KnapsackItem {
                id: "c".into(),
                weight: 3,
                value: 4.0,
            },
        ];
        let result = knapsack(&items, 2).unwrap();
        assert_eq!(result.selected_ids, ["a"]);
        assert_eq!(result.total_value, 3.0);
        assert_eq!(knapsack(&items, 5).unwrap().selected_ids, ["a", "c"]);
    }
}
