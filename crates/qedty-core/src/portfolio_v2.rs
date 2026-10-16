//! Currency-neutral portfolio optimization v2.
//!
//! This operation matches the Python reference contract. Currency conversion is
//! delegated to the same decimal-string FX boundary used by currency.convert.v2.
//! No live FX access, implicit triangulation, or binary floating-point money is used.

use crate::currency_v2::convert_money_v2;
use crate::decimal_v2::{DecimalV2, DecimalV2Error, DECIMAL_V2_PRECISION};
use crate::sha256_hex;
use crate::temporal::{parse_rfc3339, to_rfc3339};
use serde_json::{json, Value};
use std::cmp::Ordering;

type ContractError = (String, String);

const MAX_PORTFOLIO_ITEMS: usize = 4096;
const MAX_EXACT_ITEMS: usize = 28;
const MAX_EXACT_SEARCH_NODES: usize = 200_000;

fn fail(category: &str, message: impl Into<String>) -> ContractError {
    (category.to_owned(), message.into())
}

fn object_field<'a>(value: &'a Value, name: &str) -> Result<&'a Value, ContractError> {
    value
        .get(name)
        .filter(|field| field.is_object())
        .ok_or_else(|| fail("invalid_input", format!("field {name} must be an object")))
}

fn string_field<'a>(value: &'a Value, name: &str) -> Result<&'a str, ContractError> {
    value
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| fail("invalid_input", format!("field {name} must be a string")))
}

fn decimal_field(value: &Value, name: &str) -> Result<DecimalV2, ContractError> {
    let text = string_field(value, name)?;
    DecimalV2::parse(text).map_err(decimal_error)
}

fn decimal_error(error: DecimalV2Error) -> ContractError {
    let message = error.to_string();
    let category = if message == "division by zero" {
        "division_by_zero"
    } else {
        "invalid_number"
    };
    fail(category, message)
}

fn decimal_text(value: &DecimalV2) -> String {
    value.format_canonical()
}

fn time_text(value: &str, field: &str) -> Result<String, ContractError> {
    let instant = parse_rfc3339(value)
        .map_err(|error| fail("invalid_timestamp", format!("{field}: {error}")))?;
    let fixed = to_rfc3339(instant)
        .map_err(|error| fail("invalid_timestamp", format!("{field}: {error}")))?;
    Ok(fixed.replace(".000000Z", "Z"))
}

fn money_payload(value: &Value) -> Result<Value, ContractError> {
    let amount = decimal_field(value, "amount")?;
    if amount.is_negative() {
        return Err(fail("invalid_money", "money amount must be non-negative"));
    }
    let currency_code = string_field(value, "currency_code")?;
    let profile_version = string_field(value, "metadata_profile_version")?;
    if currency_code.len() != 3 || !currency_code.bytes().all(|byte| byte.is_ascii_uppercase()) {
        return Err(fail(
            "invalid_currency",
            "currency_code must be a three-letter uppercase currency code",
        ));
    }
    if profile_version.trim().is_empty() {
        return Err(fail(
            "invalid_input",
            "metadata_profile_version must be non-empty",
        ));
    }
    Ok(json!({
        "amount": amount.format_fixed(),
        "currency_code": currency_code,
        "metadata_profile_version": profile_version,
    }))
}

fn money_with_amount(amount: &DecimalV2, currency_code: &str, profile_version: &str) -> Value {
    json!({
        "amount": amount.format_fixed(),
        "currency_code": currency_code,
        "metadata_profile_version": profile_version,
    })
}

fn normalize_profile(profile: &Value) -> Result<Value, ContractError> {
    let version = string_field(profile, "profile_version")?;
    if version.trim().is_empty() {
        return Err(fail("invalid_input", "profile_version must be non-empty"));
    }
    let raw = profile
        .get("currencies")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            fail(
                "invalid_input",
                "currency profile currencies must be an array",
            )
        })?;
    if raw.is_empty() {
        return Err(fail("invalid_input", "currency profile must not be empty"));
    }
    let mut entries = Vec::with_capacity(raw.len());
    for currency in raw {
        let code = string_field(currency, "currency_code")?.to_owned();
        let scale = currency
            .get("minor_unit_scale")
            .and_then(Value::as_u64)
            .ok_or_else(|| {
                fail(
                    "invalid_input",
                    "minor_unit_scale must be a non-negative integer",
                )
            })?;
        if scale > 9 {
            return Err(fail(
                "invalid_input",
                "minor_unit_scale must be between 0 and 9",
            ));
        }
        let rounding = string_field(currency, "rounding_mode")?.to_owned();
        entries.push((
            code,
            json!({
                "currency_code": currency.get("currency_code").cloned().unwrap_or(Value::Null),
                "minor_unit_scale": scale,
                "rounding_mode": rounding,
            }),
        ));
    }
    entries.sort_by(|left, right| left.0.cmp(&right.0));
    let mut seen = std::collections::BTreeSet::new();
    for (code, _) in &entries {
        if !seen.insert(code.clone()) {
            return Err(fail(
                "invalid_input",
                "currency metadata profile contains duplicate currency codes",
            ));
        }
    }
    Ok(json!({
        "profile_version": version,
        "currencies": entries.into_iter().map(|entry| entry.1).collect::<Vec<_>>(),
    }))
}

fn currency_metadata<'a>(
    profile: &'a Value,
    currency_code: &str,
) -> Result<(u32, &'a str), ContractError> {
    let currencies = profile
        .get("currencies")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            fail(
                "invalid_input",
                "currency profile currencies must be an array",
            )
        })?;
    for entry in currencies {
        if entry.get("currency_code").and_then(Value::as_str) == Some(currency_code) {
            let scale = entry
                .get("minor_unit_scale")
                .and_then(Value::as_u64)
                .ok_or_else(|| fail("invalid_input", "minor_unit_scale must be an integer"))?;
            let scale = u32::try_from(scale)
                .map_err(|_| fail("invalid_input", "minor_unit_scale is out of range"))?;
            let rounding = string_field(entry, "rounding_mode")?;
            return Ok((scale, rounding));
        }
    }
    Err(fail(
        "invalid_currency",
        format!("currency {currency_code} is absent from the supplied metadata profile"),
    ))
}

fn normalize_fx_snapshot(snapshot: Option<&Value>) -> Result<Value, ContractError> {
    let Some(snapshot) = snapshot else {
        return Ok(Value::Null);
    };
    if snapshot.is_null() {
        return Ok(Value::Null);
    }
    let snapshot_id = string_field(snapshot, "snapshot_id")?;
    let as_of = time_text(string_field(snapshot, "as_of")?, "as_of")?;
    let valid_from = time_text(string_field(snapshot, "valid_from")?, "valid_from")?;
    let valid_to = time_text(string_field(snapshot, "valid_to")?, "valid_to")?;
    let rates = snapshot
        .get("rates")
        .and_then(Value::as_array)
        .ok_or_else(|| fail("invalid_fx_snapshot", "rates must be an array"))?;
    let mut normalized = Vec::with_capacity(rates.len());
    for rate in rates {
        normalized.push(json!({
            "base_currency": string_field(rate, "base_currency")?,
            "quote_currency": string_field(rate, "quote_currency")?,
            "rate": decimal_text(&decimal_field(rate, "rate")?),
            "observed_at": time_text(string_field(rate, "observed_at")?, "observed_at")?,
            "source": string_field(rate, "source")?,
            "provenance_id": string_field(rate, "provenance_id")?,
        }));
    }
    normalized.sort_by(|left, right| {
        let left_key = (
            left.get("base_currency")
                .and_then(Value::as_str)
                .unwrap_or(""),
            left.get("quote_currency")
                .and_then(Value::as_str)
                .unwrap_or(""),
        );
        let right_key = (
            right
                .get("base_currency")
                .and_then(Value::as_str)
                .unwrap_or(""),
            right
                .get("quote_currency")
                .and_then(Value::as_str)
                .unwrap_or(""),
        );
        left_key.cmp(&right_key)
    });
    Ok(json!({
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "rates": normalized,
    }))
}

fn conversion_request(
    source: &Value,
    target_currency: &str,
    profile: &Value,
    snapshot: Option<&Value>,
) -> Value {
    json!({
        "schema_version": "2.0",
        "source": source,
        "target_currency_code": target_currency,
        "currency_profile": profile,
        "fx_snapshot": snapshot.cloned().unwrap_or(Value::Null),
    })
}

fn convert_cost(
    source: &Value,
    target_currency: &str,
    profile: &Value,
    snapshot: Option<&Value>,
) -> Result<Value, ContractError> {
    convert_money_v2(&conversion_request(
        source,
        target_currency,
        profile,
        snapshot,
    ))
}

fn target_money(conversion: &Value) -> Result<Value, ContractError> {
    conversion
        .get("target")
        .filter(|value| value.is_object())
        .cloned()
        .ok_or_else(|| {
            fail(
                "invalid_input",
                "currency conversion result lacks target money",
            )
        })
}

fn target_amount(conversion: &Value) -> Result<DecimalV2, ContractError> {
    decimal_field(
        conversion
            .get("target")
            .ok_or_else(|| fail("invalid_input", "currency conversion result lacks target"))?,
        "amount",
    )
}

fn decimal_sum(values: &[DecimalV2]) -> DecimalV2 {
    let mut total = DecimalV2::zero();
    for value in values {
        total = total.add(value);
    }
    total
}

fn cvar(scores: &[DecimalV2], alpha: &DecimalV2) -> Result<DecimalV2, ContractError> {
    if scores.is_empty() {
        return Ok(DecimalV2::zero());
    }
    let zero = DecimalV2::zero();
    let one = DecimalV2::one();
    if alpha.compare(&zero) != Ordering::Greater || alpha.compare(&one) != Ordering::Less {
        return Err(fail("invalid_input", "cvar_alpha must be in (0, 1)"));
    }
    let mut ordered = scores.to_vec();
    ordered.sort_by(DecimalV2::compare);
    let one_minus_alpha = one.subtract(alpha);
    let tail_fraction = one_minus_alpha.multiply(&DecimalV2::from_u64(ordered.len() as u64));
    let tail_text = tail_fraction.format_canonical();
    let mut parts = tail_text.split('.');
    let whole = parts.next().unwrap_or("0").parse::<usize>().unwrap_or(0);
    let fraction = parts.next().unwrap_or("");
    let tail_size = (whole + usize::from(fraction.bytes().any(|byte| byte != b'0')))
        .max(1)
        .min(ordered.len());
    let tail_sum = decimal_sum(&ordered[..tail_size]);
    tail_sum
        .divide(&DecimalV2::from_u64(tail_size as u64), DECIMAL_V2_PRECISION)
        .map_err(decimal_error)
}

fn dominance(scores: &[DecimalV2]) -> Result<DecimalV2, ContractError> {
    if scores.is_empty() {
        return Ok(DecimalV2::zero());
    }
    let total = decimal_sum(scores);
    let mean = total
        .divide(
            &DecimalV2::from_u64(scores.len() as u64),
            DECIMAL_V2_PRECISION,
        )
        .map_err(decimal_error)?;
    if mean.is_zero() {
        return Ok(DecimalV2::one());
    }
    let minimum = scores
        .iter()
        .min_by(|left, right| left.compare(right))
        .cloned()
        .unwrap_or_else(DecimalV2::zero);
    minimum
        .divide(&mean, DECIMAL_V2_PRECISION)
        .map_err(decimal_error)
}

fn minimum_score(scores: &[DecimalV2]) -> DecimalV2 {
    scores
        .iter()
        .min_by(|left, right| left.compare(right))
        .cloned()
        .unwrap_or_else(DecimalV2::zero)
}

#[derive(Clone)]
struct Candidate {
    id: String,
    source_cost: Value,
    reporting_cost: Value,
    cost: DecimalV2,
    gain: DecimalV2,
    risk: DecimalV2,
    scenario_scores: Vec<DecimalV2>,
    rationale: String,
    conversion: Value,
    robust_score: DecimalV2,
    efficiency: DecimalV2,
    utility: DecimalV2,
}

struct ObjectiveConfig<'a> {
    kind: &'a str,
    gain_weight: &'a DecimalV2,
    cost_weight: &'a DecimalV2,
    risk_weight: &'a DecimalV2,
    cvar_alpha: &'a DecimalV2,
}

fn candidate_utility(
    gain: &DecimalV2,
    cost: &DecimalV2,
    risk: &DecimalV2,
    scenario_scores: &[DecimalV2],
    objective: &ObjectiveConfig<'_>,
) -> Result<(DecimalV2, DecimalV2, DecimalV2), ContractError> {
    let million = DecimalV2::parse("1000000").map_err(decimal_error)?;
    let cost_millions = cost
        .divide(&million, DECIMAL_V2_PRECISION)
        .map_err(decimal_error)?;
    let efficiency = if cost.is_zero() {
        gain.clone()
    } else {
        gain.divide(&cost_millions, DECIMAL_V2_PRECISION)
            .map_err(decimal_error)?
    };
    let robust = if scenario_scores.is_empty() {
        gain.clone()
    } else {
        minimum_score(scenario_scores)
    };
    let utility = match objective.kind {
        "continuity_gain" => gain.clone(),
        "weighted_score" => objective.gain_weight
            .multiply(gain)
            .subtract(&objective.cost_weight.multiply(&cost_millions))
            .subtract(&objective.risk_weight.multiply(risk)),
        "robust_floor" => robust.clone(),
        "lower_tail_cvar" => cvar(scenario_scores, objective.cvar_alpha)?,
        _ => {
            return Err(fail(
                "invalid_input",
                format!("unsupported objective kind {}", objective.kind),
            ))
        }
    };
    if utility.is_negative() && objective.kind == "continuity_gain" {
        return Err(fail(
            "invalid_input",
            "continuity_gain must be non-negative",
        ));
    }
    Ok((utility, robust, efficiency))
}

struct Solver<'a> {
    candidates: &'a [Candidate],
    ordered: Vec<usize>,
    scenario_count: usize,
    objective_kind: &'a str,
    cvar_alpha: &'a DecimalV2,
    available_budget: DecimalV2,
    nodes: usize,
    exhausted: bool,
    best_ids: Vec<String>,
    best_value: DecimalV2,
    best_spent: DecimalV2,
}

impl<'a> Solver<'a> {
    fn portfolio_value(&self, ids: &[String]) -> Result<DecimalV2, ContractError> {
        if self.objective_kind != "robust_floor" && self.objective_kind != "lower_tail_cvar" {
            let values: Vec<DecimalV2> = ids
                .iter()
                .filter_map(|id| self.candidates.iter().find(|item| &item.id == id))
                .map(|item| item.utility.clone())
                .collect();
            return Ok(decimal_sum(&values));
        }
        let mut totals = vec![DecimalV2::zero(); self.scenario_count];
        for id in ids {
            if let Some(item) = self.candidates.iter().find(|candidate| &candidate.id == id) {
                for (index, score) in item.scenario_scores.iter().enumerate() {
                    totals[index] = totals[index].add(score);
                }
            }
        }
        if self.objective_kind == "robust_floor" {
            Ok(minimum_score(&totals))
        } else {
            cvar(&totals, self.cvar_alpha)
        }
    }

    fn spent_for(&self, ids: &[String]) -> DecimalV2 {
        let costs: Vec<DecimalV2> = ids
            .iter()
            .filter_map(|id| self.candidates.iter().find(|item| &item.id == id))
            .map(|item| item.cost.clone())
            .collect();
        decimal_sum(&costs)
    }

    fn consider(&mut self, ids: &[String]) -> Result<(), ContractError> {
        let mut normalized = ids.to_vec();
        normalized.sort();
        let value = self.portfolio_value(&normalized)?;
        let spent = self.spent_for(&normalized);
        let better = match value.compare(&self.best_value) {
            Ordering::Greater => true,
            Ordering::Less => false,
            Ordering::Equal => match spent.compare(&self.best_spent) {
                Ordering::Less => true,
                Ordering::Greater => false,
                Ordering::Equal => normalized < self.best_ids,
            },
        };
        if better {
            self.best_ids = normalized;
            self.best_value = value;
            self.best_spent = spent;
        }
        Ok(())
    }

    fn bound_value(
        &self,
        index: usize,
        spent: &DecimalV2,
        chosen: &[String],
    ) -> Result<DecimalV2, ContractError> {
        let remaining = &self.ordered[index..];
        if self.objective_kind != "robust_floor" && self.objective_kind != "lower_tail_cvar" {
            let mut bound = self.portfolio_value(chosen)?;
            let mut remaining_budget = self.available_budget.subtract(spent);
            for candidate_index in remaining {
                let item = &self.candidates[*candidate_index];
                if item.utility.compare(&DecimalV2::zero()) != Ordering::Greater {
                    continue;
                }
                if item.cost.is_zero() {
                    bound = bound.add(&item.utility);
                } else if item.cost.compare(&remaining_budget) != Ordering::Greater {
                    bound = bound.add(&item.utility);
                    remaining_budget = remaining_budget.subtract(&item.cost);
                } else if remaining_budget.compare(&DecimalV2::zero()) == Ordering::Greater {
                    let fractional = item
                        .utility
                        .multiply(&remaining_budget)
                        .divide(&item.cost, DECIMAL_V2_PRECISION)
                        .map_err(decimal_error)?;
                    bound = bound.add(&fractional);
                    break;
                }
            }
            return Ok(bound);
        }

        let mut current_totals = vec![DecimalV2::zero(); self.scenario_count];
        for id in chosen {
            if let Some(item) = self.candidates.iter().find(|candidate| &candidate.id == id) {
                for (scenario_index, score) in item.scenario_scores.iter().enumerate() {
                    current_totals[scenario_index] = current_totals[scenario_index].add(score);
                }
            }
        }
        let zero = DecimalV2::zero();
        let mut upper_scores = Vec::with_capacity(self.scenario_count);
        for (scenario_index, current) in current_totals.iter().enumerate() {
            let mut optimistic = current.clone();
            for candidate_index in remaining {
                let score = &self.candidates[*candidate_index].scenario_scores[scenario_index];
                if score.compare(&zero) == Ordering::Greater {
                    optimistic = optimistic.add(score);
                }
            }
            upper_scores.push(optimistic);
        }
        if self.objective_kind == "robust_floor" {
            Ok(minimum_score(&upper_scores))
        } else {
            cvar(&upper_scores, self.cvar_alpha)
        }
    }

    fn search(
        &mut self,
        index: usize,
        spent: DecimalV2,
        chosen: &mut Vec<String>,
    ) -> Result<(), ContractError> {
        if self.exhausted {
            return Ok(());
        }
        if self.nodes >= MAX_EXACT_SEARCH_NODES {
            self.exhausted = true;
            return Ok(());
        }
        self.nodes += 1;
        if index >= self.ordered.len() {
            return self.consider(chosen);
        }
        if self
            .bound_value(index, &spent, chosen)?
            .compare(&self.best_value)
            == Ordering::Less
        {
            return Ok(());
        }

        let item = &self.candidates[self.ordered[index]];
        let id = item.id.clone();
        let cost = item.cost.clone();
        let remaining_budget = self.available_budget.subtract(&spent);
        if cost.compare(&remaining_budget) != Ordering::Greater {
            let next_spent = spent.add(&cost);
            chosen.push(id.clone());
            self.search(index + 1, next_spent, chosen)?;
            chosen.pop();
        }
        self.search(index + 1, spent, chosen)
    }
}

fn heuristic_cmp(left: &Candidate, right: &Candidate) -> Ordering {
    match (left.cost.is_zero(), right.cost.is_zero()) {
        (true, false) => Ordering::Less,
        (false, true) => Ordering::Greater,
        (true, true) => right
            .utility
            .compare(&left.utility)
            .then(left.id.cmp(&right.id)),
        (false, false) => {
            let left_ratio = left
                .utility
                .divide(&left.cost, DECIMAL_V2_PRECISION)
                .unwrap_or_else(|_| DecimalV2::zero());
            let right_ratio = right
                .utility
                .divide(&right.cost, DECIMAL_V2_PRECISION)
                .unwrap_or_else(|_| DecimalV2::zero());
            right_ratio
                .compare(&left_ratio)
                .then(left.id.cmp(&right.id))
        }
    }
}

fn greedy_select(candidates: &[Candidate], indices: &[usize], budget: &DecimalV2) -> Vec<String> {
    let zero = DecimalV2::zero();
    let mut ordered: Vec<usize> = indices
        .iter()
        .copied()
        .filter(|index| {
            candidates[*index].cost.compare(budget) != Ordering::Greater
                && candidates[*index].utility.compare(&zero) == Ordering::Greater
        })
        .collect();
    ordered.sort_by(|left, right| heuristic_cmp(&candidates[*left], &candidates[*right]));
    let mut spent = DecimalV2::zero();
    let mut chosen = Vec::new();
    for index in ordered {
        let candidate = &candidates[index];
        let remaining = budget.subtract(&spent);
        if candidate.cost.compare(&remaining) != Ordering::Greater {
            spent = spent.add(&candidate.cost);
            chosen.push(candidate.id.clone());
        }
    }
    chosen.sort();
    chosen
}

type PortfolioSelection = (Vec<String>, DecimalV2, DecimalV2, String, String, usize);

fn select_portfolio(
    candidates: &[Candidate],
    available_budget: &DecimalV2,
    kind: &str,
    cvar_alpha: &DecimalV2,
    scenario_count: usize,
) -> Result<PortfolioSelection, ContractError> {
    let zero = DecimalV2::zero();
    let non_additive = kind == "robust_floor" || kind == "lower_tail_cvar";
    let mut indices: Vec<usize> = candidates
        .iter()
        .enumerate()
        .filter(|(_, candidate)| candidate.cost.compare(available_budget) != Ordering::Greater)
        .filter(|(_, candidate)| {
            non_additive || candidate.utility.compare(&zero) == Ordering::Greater
        })
        .map(|(index, _)| index)
        .collect();

    let greedy_ids = greedy_select(candidates, &indices, available_budget);
    let mut solver = Solver {
        candidates,
        ordered: Vec::new(),
        scenario_count,
        objective_kind: kind,
        cvar_alpha,
        available_budget: available_budget.clone(),
        nodes: 0,
        exhausted: false,
        best_ids: Vec::new(),
        best_value: DecimalV2::zero(),
        best_spent: DecimalV2::zero(),
    };
    solver.consider(&greedy_ids)?;

    if indices.len() > MAX_EXACT_ITEMS {
        return Ok((
            solver.best_ids,
            solver.best_value,
            solver.best_spent,
            "feasible_not_proven_optimal".to_owned(),
            "greedy_fallback".to_owned(),
            0,
        ));
    }

    indices.sort_by(|left, right| heuristic_cmp(&candidates[*left], &candidates[*right]));
    solver.ordered = indices;
    solver.search(0, DecimalV2::zero(), &mut Vec::new())?;
    let status = if solver.exhausted {
        "feasible_not_proven_optimal"
    } else {
        "optimal"
    };
    let mode = if solver.exhausted {
        "node_limit_fallback"
    } else {
        "exact_branch_and_bound"
    };
    Ok((
        solver.best_ids,
        solver.best_value,
        solver.best_spent,
        status.to_owned(),
        mode.to_owned(),
        solver.nodes,
    ))
}

/// Evaluate the v2 currency-neutral portfolio request and return the versioned result JSON.
pub fn optimize_portfolio_v2(request: &Value) -> Result<Value, ContractError> {
    if string_field(request, "schema_version")? != "2.0" {
        return Err(fail(
            "invalid_schema_version",
            "schema_version must equal '2.0'",
        ));
    }
    let budget_input = object_field(request, "budget")?;
    let budget = money_payload(budget_input)?;
    let budget_amount = decimal_field(&budget, "amount")?;
    let reporting_currency = string_field(&budget, "currency_code")?.to_owned();
    let profile_input = object_field(request, "currency_profile")?;
    let profile_version = string_field(profile_input, "profile_version")?.to_owned();
    let profile = normalize_profile(profile_input)?;
    let snapshot_input = match request.get("fx_snapshot") {
        None | Some(Value::Null) => None,
        Some(value) if value.is_object() => Some(value),
        Some(_) => {
            return Err(fail(
                "invalid_fx_snapshot",
                "fx_snapshot must be an object or null",
            ))
        }
    };
    let normalized_snapshot = normalize_fx_snapshot(snapshot_input)?;
    // Validate the reporting budget against the exact same versioned metadata
    // boundary as candidate costs, including scale and currency-profile identity.
    let _budget_validation = convert_cost(&budget, &reporting_currency, &profile, snapshot_input)?;
    let fx_snapshot_id = snapshot_input
        .and_then(|value| value.get("snapshot_id"))
        .and_then(Value::as_str)
        .map(str::to_owned);

    let raw_scenario_ids = request
        .get("scenario_ids")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut scenario_ids = Vec::with_capacity(raw_scenario_ids.len());
    let mut seen_scenarios = std::collections::BTreeSet::new();
    for value in raw_scenario_ids {
        let id = value
            .as_str()
            .ok_or_else(|| fail("invalid_input", "scenario IDs must be strings"))?
            .to_owned();
        if id.trim().is_empty() || !seen_scenarios.insert(id.clone()) {
            return Err(fail(
                "invalid_input",
                "scenario IDs must be nonblank and unique",
            ));
        }
        scenario_ids.push(id);
    }

    let objective = request
        .get("objective")
        .filter(|value| value.is_object())
        .cloned()
        .unwrap_or_else(|| json!({}));
    let kind = objective
        .get("kind")
        .and_then(Value::as_str)
        .unwrap_or("weighted_score")
        .to_owned();
    if ![
        "continuity_gain",
        "weighted_score",
        "robust_floor",
        "lower_tail_cvar",
    ]
    .contains(&kind.as_str())
    {
        return Err(fail(
            "invalid_input",
            format!("unsupported v2 objective kind: {kind}"),
        ));
    }
    let gain_weight = objective
        .get("gain_weight")
        .and_then(Value::as_str)
        .map(DecimalV2::parse)
        .transpose()
        .map_err(decimal_error)?
        .unwrap_or_else(DecimalV2::one);
    let cost_weight = objective
        .get("cost_weight")
        .and_then(Value::as_str)
        .map(DecimalV2::parse)
        .transpose()
        .map_err(decimal_error)?
        .unwrap_or_else(DecimalV2::one);
    let risk_weight = objective
        .get("risk_weight")
        .and_then(Value::as_str)
        .map(DecimalV2::parse)
        .transpose()
        .map_err(decimal_error)?
        .unwrap_or_else(DecimalV2::one);
    let cvar_alpha = objective
        .get("cvar_alpha")
        .and_then(Value::as_str)
        .map(DecimalV2::parse)
        .transpose()
        .map_err(decimal_error)?
        .unwrap_or_else(|| DecimalV2::parse("0.9").expect("valid constant"));
    for (label, value) in [
        ("gain_weight", &gain_weight),
        ("cost_weight", &cost_weight),
        ("risk_weight", &risk_weight),
    ] {
        if value.is_negative() {
            return Err(fail(
                "invalid_input",
                format!("{label} must be non-negative"),
            ));
        }
    }
    let zero = DecimalV2::zero();
    let one = DecimalV2::one();
    if cvar_alpha.compare(&zero) != Ordering::Greater || cvar_alpha.compare(&one) != Ordering::Less
    {
        return Err(fail("invalid_input", "cvar_alpha must be in (0, 1)"));
    }

    let raw_candidates = request
        .get("candidates")
        .and_then(Value::as_array)
        .ok_or_else(|| fail("invalid_input", "candidates must be an array"))?;
    if raw_candidates.len() > MAX_PORTFOLIO_ITEMS {
        return Err(fail(
            "resource_limit",
            "candidate count exceeds resource limit 4096",
        ));
    }
    let mut candidates = Vec::with_capacity(raw_candidates.len());
    let mut seen_candidates = std::collections::BTreeSet::new();
    for raw in raw_candidates {
        let id = string_field(raw, "intervention_id")?.to_owned();
        if id.trim().is_empty() || id.len() > 128 || !seen_candidates.insert(id.clone()) {
            return Err(fail(
                "invalid_input",
                "intervention IDs must be unique, nonblank and at most 128 bytes",
            ));
        }
        let source_cost = money_payload(object_field(raw, "cost")?)?;
        let conversion = convert_cost(&source_cost, &reporting_currency, &profile, snapshot_input)?;
        let reporting_cost = target_money(&conversion)?;
        let cost = target_amount(&conversion)?;
        let gain = decimal_field(raw, "continuity_gain")?;
        let risk = match raw.get("risk_score") {
            None => DecimalV2::zero(),
            Some(_) => decimal_field(raw, "risk_score")?,
        };
        if gain.is_negative() || risk.is_negative() {
            return Err(fail(
                "invalid_input",
                "continuity_gain and risk_score must be non-negative",
            ));
        }
        let scenario_values = raw
            .get("scenario_scores")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut scenario_scores = Vec::with_capacity(scenario_values.len());
        for score in &scenario_values {
            let text = score
                .as_str()
                .ok_or_else(|| fail("invalid_input", "scenario scores must be decimal strings"))?;
            scenario_scores.push(DecimalV2::parse(text).map_err(decimal_error)?);
        }
        if scenario_scores.len() != scenario_ids.len() {
            return Err(fail(
                "invalid_input",
                "each candidate must provide one score per declared scenario",
            ));
        }
        let rationale = raw
            .get("rationale")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        let objective_config = ObjectiveConfig {
            kind: &kind,
            gain_weight: &gain_weight,
            cost_weight: &cost_weight,
            risk_weight: &risk_weight,
            cvar_alpha: &cvar_alpha,
        };
        let (utility, robust_score, efficiency) = candidate_utility(
            &gain,
            &cost,
            &risk,
            &scenario_scores,
            &objective_config,
        )?;
        candidates.push(Candidate {
            id,
            source_cost,
            reporting_cost,
            cost,
            gain,
            risk,
            scenario_scores,
            rationale,
            conversion,
            robust_score,
            efficiency,
            utility,
        });
    }
    if (kind == "robust_floor" || kind == "lower_tail_cvar") && scenario_ids.is_empty() {
        return Err(fail(
            "invalid_input",
            "robust_floor and lower_tail_cvar require declared scenario scores",
        ));
    }

    let fixed_overhead_input = match request.get("fixed_overhead") {
        None | Some(Value::Null) => None,
        Some(value) if value.is_object() => Some(money_payload(value)?),
        Some(_) => {
            return Err(fail(
                "invalid_input",
                "fixed_overhead must be an object or null",
            ))
        }
    };
    let overhead_source = fixed_overhead_input.clone().unwrap_or_else(|| {
        json!({
            "amount": "0",
            "currency_code": reporting_currency,
            "metadata_profile_version": profile_version,
        })
    });
    let overhead_conversion = convert_cost(
        &overhead_source,
        &reporting_currency,
        &profile,
        snapshot_input,
    )?;
    let overhead = target_money(&overhead_conversion)?;
    let overhead_amount = target_amount(&overhead_conversion)?;
    let available_budget = budget_amount.subtract(&overhead_amount);
    let infeasible = available_budget.is_negative();

    let (selected_ids, objective_value, spent_raw, status, solver_mode, solver_nodes) =
        if infeasible {
            (
                Vec::new(),
                DecimalV2::zero(),
                DecimalV2::zero(),
                "infeasible".to_owned(),
                "infeasible".to_owned(),
                0,
            )
        } else {
            select_portfolio(
                &candidates,
                &available_budget,
                &kind,
                &cvar_alpha,
                scenario_ids.len(),
            )?
        };
    let selected_set: std::collections::BTreeSet<String> = selected_ids.iter().cloned().collect();

    let mut recommendation_indices: Vec<usize> = (0..candidates.len()).collect();
    recommendation_indices.sort_by(|left, right| {
        let a = &candidates[*left];
        let b = &candidates[*right];
        b.robust_score
            .compare(&a.robust_score)
            .then_with(|| b.efficiency.compare(&a.efficiency))
            .then_with(|| a.id.cmp(&b.id))
    });
    let recommendations: Vec<Value> = recommendation_indices
        .iter()
        .map(|index| {
            let candidate = &candidates[*index];
            json!({
                "intervention_id": candidate.id,
                "source_cost": candidate.source_cost,
                "reporting_cost": candidate.reporting_cost,
                "continuity_gain": decimal_text(&candidate.gain),
                "risk_score": decimal_text(&candidate.risk),
                "scenario_scores": candidate.scenario_scores.iter().map(decimal_text).collect::<Vec<_>>(),
                "robust_score": decimal_text(&candidate.robust_score),
                "efficiency": decimal_text(&candidate.efficiency),
                "utility": decimal_text(&candidate.utility),
                "selected": selected_set.contains(&candidate.id),
                "rationale": candidate.rationale,
                "conversion": candidate.conversion,
            })
        })
        .collect();

    let (scale, rounding_mode) = currency_metadata(&profile, &reporting_currency)?;
    let spent_amount = spent_raw
        .quantize(scale, rounding_mode)
        .map_err(decimal_error)?;
    let total_committed_amount = spent_amount
        .add(&overhead_amount)
        .quantize(scale, rounding_mode)
        .map_err(decimal_error)?;
    let spent = money_with_amount(&spent_amount, &reporting_currency, &profile_version);
    let total_committed = money_with_amount(
        &total_committed_amount,
        &reporting_currency,
        &profile_version,
    );

    let mut portfolio_scores = Vec::new();
    if !scenario_ids.is_empty() && !selected_ids.is_empty() {
        for scenario_index in 0..scenario_ids.len() {
            let mut total = DecimalV2::zero();
            for id in &selected_ids {
                if let Some(candidate) = candidates.iter().find(|candidate| &candidate.id == id) {
                    total = total.add(&candidate.scenario_scores[scenario_index]);
                }
            }
            portfolio_scores.push(total);
        }
    } else {
        for id in &selected_ids {
            if let Some(candidate) = candidates.iter().find(|candidate| &candidate.id == id) {
                portfolio_scores.push(candidate.robust_score.clone());
            }
        }
    }
    let robust_floor = if portfolio_scores.is_empty() {
        DecimalV2::zero()
    } else {
        minimum_score(&portfolio_scores)
    };
    let portfolio_cvar = cvar(&portfolio_scores, &cvar_alpha)?;
    let dominance_score = dominance(&portfolio_scores)?;

    let profile_payload = profile.clone();
    let objective_payload = json!({
        "kind": kind,
        "gain_weight": decimal_text(&gain_weight),
        "cost_weight": decimal_text(&cost_weight),
        "risk_weight": decimal_text(&risk_weight),
        "cvar_alpha": decimal_text(&cvar_alpha),
    });
    let mut request_candidates: Vec<&Candidate> = candidates.iter().collect();
    request_candidates.sort_by(|left, right| left.id.cmp(&right.id));
    let request_payload = json!({
        "schema_version": "2.0",
        "budget": budget,
        "fixed_overhead": fixed_overhead_input,
        "currency_profile": profile_payload,
        "fx_snapshot": normalized_snapshot,
        "objective": objective_payload,
        "scenario_ids": scenario_ids,
        "candidates": request_candidates.iter().map(|candidate| json!({
            "intervention_id": candidate.id,
            "cost": candidate.source_cost,
            "continuity_gain": decimal_text(&candidate.gain),
            "risk_score": decimal_text(&candidate.risk),
            "scenario_scores": candidate.scenario_scores.iter().map(decimal_text).collect::<Vec<_>>(),
            "rationale": candidate.rationale,
        })).collect::<Vec<_>>(),
    });
    let result_payload = json!({
        "status": status,
        "solver_mode": solver_mode,
        "selected_intervention_ids": selected_ids,
        "budget": budget,
        "fixed_overhead": overhead,
        "spent": spent,
        "total_committed": total_committed,
        "objective_value": decimal_text(&objective_value),
        "portfolio_robust_floor": decimal_text(&robust_floor),
        "portfolio_cvar": decimal_text(&portfolio_cvar),
        "dominance_score": decimal_text(&dominance_score),
        "scenario_ids": scenario_ids,
        "solver_nodes": solver_nodes,
        "fx_snapshot_id": fx_snapshot_id,
        "recommendations": recommendations,
    });
    let digest_input = json!({"request": request_payload, "result": result_payload});
    let digest =
        sha256_hex(&digest_input).map_err(|error| fail("internal_error", error.to_string()))?;

    Ok(json!({
        "schema_version": "2.0",
        "status": status,
        "solver_mode": solver_mode,
        "objective_kind": kind,
        "reporting_currency_code": reporting_currency,
        "budget": budget,
        "fixed_overhead": overhead,
        "spent": spent,
        "total_committed": total_committed,
        "selected_intervention_ids": selected_ids,
        "recommendations": recommendations,
        "objective_value": decimal_text(&objective_value),
        "portfolio_robust_floor": decimal_text(&robust_floor),
        "portfolio_cvar": decimal_text(&portfolio_cvar),
        "dominance_score": decimal_text(&dominance_score),
        "scenario_ids": scenario_ids,
        "solver_nodes": solver_nodes,
        "fx_snapshot_id": fx_snapshot_id,
        "digest": digest,
    }))
}
