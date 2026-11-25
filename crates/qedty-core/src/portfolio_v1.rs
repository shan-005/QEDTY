//! Deterministic kernels matching QEDTY's legacy USD portfolio v1 semantics.
//!
//! This module intentionally does not implement CounterfactualEngine or the
//! application-level ResilienceOptimizer. Python remains authoritative for
//! those orchestration responsibilities. The functions here cover the pure
//! numeric and selection operations that can be compared directly.

use std::cmp::Ordering;
use std::collections::BTreeSet;

pub const MAX_EXACT_ITEMS: usize = 28;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortfolioV1Error {
    InvalidInput,
    InvalidBudget,
    InvalidItem,
    DuplicateInterventionId,
    NonFiniteObjective,
    InvalidObjectiveInputs,
    EmptyScores,
    InvalidAlpha,
    InvalidBudgetConstraint,
}

impl PortfolioV1Error {
    pub const fn category(self) -> &'static str {
        match self {
            Self::InvalidInput => "invalid_input",
            Self::InvalidBudget => "invalid_budget",
            Self::InvalidItem => "invalid_item",
            Self::DuplicateInterventionId => "duplicate_intervention_id",
            Self::NonFiniteObjective => "non_finite_objective",
            Self::InvalidObjectiveInputs => "invalid_objective_inputs",
            Self::EmptyScores => "empty_scores",
            Self::InvalidAlpha => "invalid_alpha",
            Self::InvalidBudgetConstraint => "invalid_budget_constraint",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PortfolioV1Item {
    pub intervention_id: String,
    pub cost_usd: f64,
    pub efficiency: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SolverMode {
    ExactBranchAndBound,
    GreedyFallback,
}

impl SolverMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ExactBranchAndBound => "exact_branch_and_bound",
            Self::GreedyFallback => "greedy_fallback",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SelectionStatus {
    OptimalReference,
    FeasibleNotProvenOptimal,
}

impl SelectionStatus {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::OptimalReference => "optimal_reference",
            Self::FeasibleNotProvenOptimal => "feasible_not_proven_optimal",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PortfolioV1Selection {
    pub selected_intervention_ids: Vec<String>,
    pub spent_usd: f64,
    pub objective_value: f64,
    pub solver_mode: SolverMode,
    pub status: SelectionStatus,
}

#[derive(Debug, Clone)]
struct PreparedItem {
    intervention_id: String,
    cost_usd: f64,
    efficiency: f64,
    contribution: f64,
}

fn prepare(
    items: &[PortfolioV1Item],
    budget_usd: f64,
) -> Result<Vec<PreparedItem>, PortfolioV1Error> {
    if !budget_usd.is_finite() || budget_usd < 0.0 {
        return Err(PortfolioV1Error::InvalidBudget);
    }

    let mut seen = BTreeSet::new();
    let mut prepared = Vec::with_capacity(items.len());

    for item in items {
        if item.intervention_id.trim().is_empty() {
            return Err(PortfolioV1Error::InvalidItem);
        }
        if !seen.insert(item.intervention_id.clone()) {
            return Err(PortfolioV1Error::DuplicateInterventionId);
        }
        if !item.cost_usd.is_finite() || item.cost_usd < 0.0 {
            return Err(PortfolioV1Error::InvalidItem);
        }
        if !item.efficiency.is_finite() || item.efficiency < 0.0 {
            return Err(PortfolioV1Error::InvalidItem);
        }

        // Preserve Python's operation order: efficiency * cost, then / 1e6.
        let contribution = (item.efficiency * item.cost_usd / 1_000_000.0).max(0.0);
        if !contribution.is_finite() {
            return Err(PortfolioV1Error::NonFiniteObjective);
        }

        prepared.push(PreparedItem {
            intervention_id: item.intervention_id.clone(),
            cost_usd: item.cost_usd,
            efficiency: item.efficiency,
            contribution,
        });
    }

    // Python sorts by (-efficiency, intervention_id). partial_cmp gives
    // numeric equality for +0.0 and -0.0, matching Python's float comparison.
    prepared.sort_by(|left, right| {
        right
            .efficiency
            .partial_cmp(&left.efficiency)
            .unwrap_or(Ordering::Equal)
            .then_with(|| left.intervention_id.cmp(&right.intervention_id))
    });

    let contributions: Vec<f64> = prepared.iter().map(|item| item.contribution).collect();
    let total_objective = sum_in_order(&contributions);
    if !total_objective.is_finite() {
        return Err(PortfolioV1Error::NonFiniteObjective);
    }

    Ok(prepared)
}

fn greedy_prepared(prepared: &[PreparedItem], budget_usd: f64) -> PortfolioV1Selection {
    let mut selected_intervention_ids = Vec::new();
    let mut spent_usd = 0.0_f64;
    let mut objective_value = 0.0_f64;

    for item in prepared {
        if spent_usd + item.cost_usd <= budget_usd {
            selected_intervention_ids.push(item.intervention_id.clone());
            spent_usd += item.cost_usd;
            objective_value += item.contribution;
        }
    }

    PortfolioV1Selection {
        selected_intervention_ids,
        spent_usd,
        objective_value,
        solver_mode: SolverMode::GreedyFallback,
        status: SelectionStatus::FeasibleNotProvenOptimal,
    }
}

#[derive(Debug)]
struct SearchBest {
    value: f64,
    indices: Vec<usize>,
    ids: Vec<String>,
    spent: f64,
}

fn search_exact(
    index: usize,
    spent: f64,
    value: f64,
    chosen: &mut Vec<usize>,
    prepared: &[PreparedItem],
    budget_usd: f64,
    best: &mut SearchBest,
) {
    if spent > budget_usd {
        return;
    }

    if index == prepared.len() {
        let candidate_ids: Vec<String> = chosen
            .iter()
            .map(|&position| prepared[position].intervention_id.clone())
            .collect();
        if value > best.value || (value == best.value && candidate_ids < best.ids) {
            best.value = value;
            best.indices.clone_from(chosen);
            best.ids = candidate_ids;
            best.spent = spent;
        }
        return;
    }

    // Fractional upper bound. Candidate order is descending efficiency, so
    // contribution/cost is non-increasing for positive-cost candidates.
    let mut upper_bound = value;
    let mut remaining_budget = budget_usd - spent;
    for item in &prepared[index..] {
        if item.contribution == 0.0 {
            continue;
        }
        if item.cost_usd <= remaining_budget {
            remaining_budget -= item.cost_usd;
            upper_bound += item.contribution;
        } else if item.cost_usd > 0.0 {
            upper_bound += item.contribution * (remaining_budget / item.cost_usd);
            break;
        }
    }

    // Keep equality branches: the lexicographic tie-break may still improve.
    if upper_bound < best.value {
        return;
    }

    // Branch 1: omit this item.
    search_exact(index + 1, spent, value, chosen, prepared, budget_usd, best);

    // Branch 2: include this item when it remains feasible.
    let item = &prepared[index];
    if item.cost_usd <= budget_usd - spent {
        chosen.push(index);
        search_exact(
            index + 1,
            spent + item.cost_usd,
            value + item.contribution,
            chosen,
            prepared,
            budget_usd,
            best,
        );
        chosen.pop();
    }
}

/// Select a USD portfolio using the legacy v1 utility formula and solver cutoff.
///
/// Utility contribution is max(0, efficiency * cost_usd / 1_000_000). Exact
/// branch-and-bound is used for up to 28 candidates; larger inputs use the
/// deterministic efficiency-ordered greedy fallback.
pub fn select_portfolio(
    items: &[PortfolioV1Item],
    budget_usd: f64,
) -> Result<PortfolioV1Selection, PortfolioV1Error> {
    let prepared = prepare(items, budget_usd)?;

    if prepared.len() > MAX_EXACT_ITEMS {
        return Ok(greedy_prepared(&prepared, budget_usd));
    }

    let mut best = SearchBest {
        value: -1.0,
        indices: Vec::new(),
        ids: Vec::new(),
        spent: 0.0,
    };
    let mut chosen = Vec::new();
    search_exact(0, 0.0, 0.0, &mut chosen, &prepared, budget_usd, &mut best);

    let selected_intervention_ids = best
        .indices
        .iter()
        .map(|&position| prepared[position].intervention_id.clone())
        .collect();

    Ok(PortfolioV1Selection {
        selected_intervention_ids,
        spent_usd: best.spent,
        objective_value: best.value,
        solver_mode: SolverMode::ExactBranchAndBound,
        status: SelectionStatus::OptimalReference,
    })
}

/// Deterministic greedy selection, retaining the v1 zero-cost behavior.
pub fn greedy_portfolio(
    items: &[PortfolioV1Item],
    budget_usd: f64,
) -> Result<PortfolioV1Selection, PortfolioV1Error> {
    let prepared = prepare(items, budget_usd)?;
    Ok(greedy_prepared(&prepared, budget_usd))
}

pub fn efficiency(gain: f64, cost_usd: f64) -> Result<f64, PortfolioV1Error> {
    if gain < 0.0 || cost_usd < 0.0 || !gain.is_finite() || !cost_usd.is_finite() {
        return Err(PortfolioV1Error::InvalidObjectiveInputs);
    }
    Ok(if cost_usd == 0.0 {
        gain
    } else {
        gain / (cost_usd / 1_000_000.0)
    })
}

pub fn weighted_score(
    gain: f64,
    cost_usd: f64,
    risk: f64,
    gain_weight: f64,
    cost_weight: f64,
    risk_weight: f64,
) -> Result<f64, PortfolioV1Error> {
    let inputs = [gain, cost_usd, risk, gain_weight, cost_weight, risk_weight];
    if inputs
        .iter()
        .any(|value| !value.is_finite() || *value < 0.0)
    {
        return Err(PortfolioV1Error::InvalidObjectiveInputs);
    }
    Ok(gain_weight * gain - cost_weight * (cost_usd / 1_000_000.0) - risk_weight * risk)
}

fn lower_tail_count(length: usize, alpha: f64) -> Result<usize, PortfolioV1Error> {
    if !(0.0 < alpha && alpha < 1.0) {
        return Err(PortfolioV1Error::InvalidAlpha);
    }
    // Match the current Python formula exactly rather than substituting a
    // superficially equivalent ceil operation with different edge rounding.
    let count = (((1.0 - alpha) * length as f64) + 0.999999) as usize;
    Ok(count.max(1))
}

fn sum_in_order(values: &[f64]) -> f64 {
    // CPython 3.12's built-in sum() uses Neumaier compensated summation for
    // float iterables. Mirror that behavior for cvar(), dominance_score(), and
    // the Python reference's finite-total validation in prepare().
    let mut total = 0.0_f64;
    let mut compensation = 0.0_f64;

    for &value in values {
        let next = total + value;
        if total.abs() >= value.abs() {
            compensation += (total - next) + value;
        } else {
            compensation += (value - next) + total;
        }
        total = next;
    }

    // CPython only adds a finite compensation term. This avoids turning an
    // already-overflowed sum into NaN through an infinite compensation value.
    if compensation.is_finite() {
        total + compensation
    } else {
        total
    }
}

pub fn cvar(scores: &[f64], alpha: f64) -> Result<f64, PortfolioV1Error> {
    if scores.is_empty() {
        return Err(PortfolioV1Error::EmptyScores);
    }
    let count = lower_tail_count(scores.len(), alpha)?;
    let mut ordered = scores.to_vec();
    ordered.sort_by(|left, right| left.partial_cmp(right).unwrap_or(Ordering::Equal));
    Ok(sum_in_order(&ordered[..count]) / count as f64)
}

pub fn robust_floor(scores: &[f64]) -> f64 {
    let Some((&first, rest)) = scores.split_first() else {
        return 0.0;
    };
    rest.iter().fold(
        first,
        |current, score| {
            if *score < current {
                *score
            } else {
                current
            }
        },
    )
}

pub fn cvar_score(scores: &[f64], alpha: f64) -> Result<f64, PortfolioV1Error> {
    if scores.is_empty() {
        return Ok(0.0);
    }
    cvar(scores, alpha)
}

pub fn dominance_score(scores: &[f64]) -> f64 {
    if scores.is_empty() {
        return 0.0;
    }
    let mean = sum_in_order(scores) / scores.len() as f64;
    if mean == 0.0 {
        return 1.0;
    }
    robust_floor(scores) / mean
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PortfolioBudgetConstraint {
    pub budget_usd: f64,
    pub fixed_overhead_usd: f64,
}

impl PortfolioBudgetConstraint {
    pub fn new(budget_usd: f64, fixed_overhead_usd: f64) -> Result<Self, PortfolioV1Error> {
        if !budget_usd.is_finite()
            || !fixed_overhead_usd.is_finite()
            || budget_usd < 0.0
            || fixed_overhead_usd < 0.0
        {
            return Err(PortfolioV1Error::InvalidBudgetConstraint);
        }
        Ok(Self {
            budget_usd,
            fixed_overhead_usd,
        })
    }

    pub fn permits(&self, cost_usd: f64, spent_usd: f64) -> bool {
        if !cost_usd.is_finite() || !spent_usd.is_finite() || cost_usd < 0.0 || spent_usd < 0.0 {
            return false;
        }
        spent_usd + cost_usd + self.fixed_overhead_usd <= self.budget_usd
    }
}

pub fn feasible(cost_usd: f64, budget_usd: f64) -> bool {
    if !budget_usd.is_finite() || !cost_usd.is_finite() || budget_usd < 0.0 || cost_usd < 0.0 {
        return false;
    }
    cost_usd <= budget_usd
}

#[cfg(test)]
mod tests {
    use super::{
        cvar, cvar_score, dominance_score, efficiency, feasible, greedy_portfolio, robust_floor,
        select_portfolio, weighted_score, PortfolioBudgetConstraint, PortfolioV1Error,
        PortfolioV1Item, SelectionStatus, SolverMode, MAX_EXACT_ITEMS,
    };

    fn item(id: &str, cost_usd: f64, efficiency: f64) -> PortfolioV1Item {
        PortfolioV1Item {
            intervention_id: id.to_owned(),
            cost_usd,
            efficiency,
        }
    }

    #[test]
    fn exact_solver_matches_legacy_objective_and_combination() {
        let result = select_portfolio(
            &[
                item("a", 5.0, 10.0),
                item("b", 7.0, 8.0),
                item("c", 3.0, 10.0),
            ],
            8.0,
        )
        .unwrap();
        assert_eq!(result.selected_intervention_ids, vec!["a", "c"]);
        assert_eq!(result.spent_usd, 8.0);
        assert_eq!(result.objective_value, 80.0 / 1_000_000.0);
        assert_eq!(result.solver_mode, SolverMode::ExactBranchAndBound);
        assert_eq!(result.status, SelectionStatus::OptimalReference);
    }

    #[test]
    fn exact_zero_cost_candidate_is_not_selected_but_greedy_fallback_selects_it() {
        let free = item("free", 0.0, 5.0);
        let exact = select_portfolio(std::slice::from_ref(&free), 0.0).unwrap();
        assert!(exact.selected_intervention_ids.is_empty());
        assert_eq!(exact.spent_usd, 0.0);

        let fallback_items: Vec<_> = (0..=MAX_EXACT_ITEMS)
            .map(|index| item(&format!("free-{index:02}"), 0.0, 1.0))
            .collect();
        let fallback = select_portfolio(&fallback_items, 0.0).unwrap();
        assert_eq!(
            fallback.selected_intervention_ids.len(),
            MAX_EXACT_ITEMS + 1
        );
        assert_eq!(fallback.status, SelectionStatus::FeasibleNotProvenOptimal);
        assert_eq!(fallback.solver_mode, SolverMode::GreedyFallback);
    }

    #[test]
    fn fallback_threshold_is_inclusive_at_28_and_switches_at_29() {
        let exact_items: Vec<_> = (0..MAX_EXACT_ITEMS)
            .map(|index| {
                item(
                    &format!("item-{index:02}"),
                    if index == 0 { 10.0 } else { 11.0 },
                    (MAX_EXACT_ITEMS - index) as f64,
                )
            })
            .collect();
        let exact = select_portfolio(&exact_items, 10.0).unwrap();
        assert_eq!(exact.solver_mode, SolverMode::ExactBranchAndBound);
        assert_eq!(exact.selected_intervention_ids, vec!["item-00"]);

        let fallback_items: Vec<_> = (0..=MAX_EXACT_ITEMS)
            .map(|index| {
                item(
                    &format!("item-{index:02}"),
                    if index == 0 { 10.0 } else { 11.0 },
                    (MAX_EXACT_ITEMS + 1 - index) as f64,
                )
            })
            .collect();
        let fallback = select_portfolio(&fallback_items, 10.0).unwrap();
        assert_eq!(fallback.solver_mode, SolverMode::GreedyFallback);
        assert_eq!(fallback.selected_intervention_ids, vec!["item-00"]);
    }

    #[test]
    fn ties_use_lexicographic_id_sequence() {
        let result = select_portfolio(&[item("b", 5.0, 10.0), item("a", 5.0, 10.0)], 5.0).unwrap();
        assert_eq!(result.selected_intervention_ids, vec!["a"]);
    }

    #[test]
    fn objective_and_robustness_helpers_match_v1_formulas() {
        assert_eq!(efficiency(0.5, 1_000_000.0).unwrap(), 0.5);
        assert_eq!(efficiency(5.0, 0.0).unwrap(), 5.0);
        assert_eq!(
            weighted_score(10.0, 2_000_000.0, 1.0, 1.0, 1.0, 1.0).unwrap(),
            7.0
        );
        assert_eq!(cvar(&[1.0, 2.0, 3.0], 0.9).unwrap(), 1.0);
        assert_eq!(robust_floor(&[1.0, 2.0, 3.0]), 1.0);
        assert_eq!(cvar_score(&[], 0.9).unwrap(), 0.0);
        assert_eq!(dominance_score(&[2.0, 2.0]), 1.0);
        assert_eq!(dominance_score(&[]), 0.0);
    }

    #[test]
    fn objective_and_constraint_validation_matches_v1_boundaries() {
        assert_eq!(
            efficiency(-1.0, 1.0),
            Err(PortfolioV1Error::InvalidObjectiveInputs)
        );
        assert_eq!(cvar(&[], 0.9), Err(PortfolioV1Error::EmptyScores));
        assert_eq!(cvar(&[1.0], 1.0), Err(PortfolioV1Error::InvalidAlpha));
        let constraint = PortfolioBudgetConstraint::new(100.0, 10.0).unwrap();
        assert!(constraint.permits(80.0, 0.0));
        assert!(!constraint.permits(-1.0, 0.0));
        assert!(!feasible(-1.0, 100.0));
        assert!(feasible(100.0, 100.0));
        assert_eq!(
            PortfolioBudgetConstraint::new(-1.0, 0.0),
            Err(PortfolioV1Error::InvalidBudgetConstraint)
        );
    }

    #[test]
    fn invalid_candidate_and_budget_are_rejected() {
        assert_eq!(
            select_portfolio(&[], -1.0),
            Err(PortfolioV1Error::InvalidBudget)
        );
        assert_eq!(
            select_portfolio(&[item("", 1.0, 1.0)], 1.0),
            Err(PortfolioV1Error::InvalidItem)
        );
        assert_eq!(
            select_portfolio(&[item("same", 1.0, 1.0), item("same", 2.0, 2.0)], 3.0),
            Err(PortfolioV1Error::DuplicateInterventionId)
        );
        assert_eq!(
            select_portfolio(&[item("bad", -1.0, 1.0)], 3.0),
            Err(PortfolioV1Error::InvalidItem)
        );
        assert_eq!(
            greedy_portfolio(&[item("bad", 1.0, -1.0)], 3.0),
            Err(PortfolioV1Error::InvalidItem)
        );
    }
}
