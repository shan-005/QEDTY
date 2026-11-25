//! JSONL conformance runner for QEDTY's deterministic legacy USD portfolio v1 kernels.
//!
//! Request:  {"case_id":"...","operation":"portfolio.select.v1","input":{...}}
//! Response: {"case_id":"...","ok":true,"result":{...}}
//! Diagnostics are written to stderr; stdout contains JSONL only.

use qedty_core::portfolio_v1::{
    cvar, cvar_score, dominance_score, efficiency, feasible, robust_floor, select_portfolio,
    weighted_score, PortfolioBudgetConstraint, PortfolioV1Error, PortfolioV1Item,
};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

fn string_field<'a>(input: &'a Value, name: &str) -> Result<&'a str, PortfolioV1Error> {
    input
        .get(name)
        .and_then(Value::as_str)
        .ok_or(PortfolioV1Error::InvalidInput)
}

fn number_field(input: &Value, name: &str) -> Result<f64, PortfolioV1Error> {
    input
        .get(name)
        .and_then(Value::as_f64)
        .ok_or(PortfolioV1Error::InvalidInput)
}

fn optional_number(input: &Value, name: &str, default: f64) -> Result<f64, PortfolioV1Error> {
    match input.get(name) {
        None | Some(Value::Null) => Ok(default),
        Some(value) => value.as_f64().ok_or(PortfolioV1Error::InvalidInput),
    }
}

fn scores_field(input: &Value) -> Result<Vec<f64>, PortfolioV1Error> {
    let raw = input
        .get("scores")
        .and_then(Value::as_array)
        .ok_or(PortfolioV1Error::InvalidInput)?;
    raw.iter()
        .map(|value| value.as_f64().ok_or(PortfolioV1Error::InvalidInput))
        .collect()
}

fn select_v1(input: &Value) -> Result<Value, PortfolioV1Error> {
    let budget_usd = number_field(input, "budget_usd")?;
    let raw_items = input
        .get("items")
        .and_then(Value::as_array)
        .ok_or(PortfolioV1Error::InvalidInput)?;

    let mut items = Vec::with_capacity(raw_items.len());
    for raw in raw_items {
        if !raw.is_object() {
            return Err(PortfolioV1Error::InvalidInput);
        }
        items.push(PortfolioV1Item {
            intervention_id: string_field(raw, "intervention_id")?.to_owned(),
            cost_usd: number_field(raw, "cost_usd")?,
            efficiency: number_field(raw, "efficiency")?,
        });
    }

    let selection = select_portfolio(&items, budget_usd)?;
    Ok(json!({
        "selected_intervention_ids": selection.selected_intervention_ids,
        "spent_usd": selection.spent_usd,
        "objective_value": selection.objective_value,
        "solver_mode": selection.solver_mode.as_str(),
        "status": selection.status.as_str(),
    }))
}

fn helper_v1(input: &Value) -> Result<Value, PortfolioV1Error> {
    let function = string_field(input, "function")?;
    let result = match function {
        "efficiency" => json!(efficiency(
            number_field(input, "gain")?,
            number_field(input, "cost_usd")?,
        )?),
        "weighted_score" => json!(weighted_score(
            number_field(input, "gain")?,
            number_field(input, "cost_usd")?,
            optional_number(input, "risk", 0.0)?,
            optional_number(input, "gain_weight", 1.0)?,
            optional_number(input, "cost_weight", 1.0)?,
            optional_number(input, "risk_weight", 1.0)?,
        )?),
        "cvar" => json!(cvar(
            &scores_field(input)?,
            optional_number(input, "alpha", 0.9)?,
        )?),
        "robust_floor" => json!(robust_floor(&scores_field(input)?)),
        "cvar_score" => json!(cvar_score(
            &scores_field(input)?,
            optional_number(input, "alpha", 0.9)?,
        )?),
        "dominance_score" => json!(dominance_score(&scores_field(input)?)),
        "budget_permits" => {
            let constraint = PortfolioBudgetConstraint::new(
                number_field(input, "budget_usd")?,
                optional_number(input, "fixed_overhead_usd", 0.0)?,
            )?;
            json!(constraint.permits(
                number_field(input, "cost_usd")?,
                optional_number(input, "spent_usd", 0.0)?,
            ))
        }
        "feasible" => json!(feasible(
            number_field(input, "cost_usd")?,
            number_field(input, "budget_usd")?,
        )),
        _ => return Err(PortfolioV1Error::InvalidInput),
    };
    Ok(result)
}

fn execute(operation: &str, input: &Value) -> Result<Value, PortfolioV1Error> {
    match operation {
        "portfolio.select.v1" => select_v1(input),
        "portfolio.helper.v1" => helper_v1(input),
        _ => Err(PortfolioV1Error::InvalidInput),
    }
}

fn handle_line(line: &str) -> Value {
    let request: Value = match serde_json::from_str(line) {
        Ok(value) => value,
        Err(_) => {
            return json!({
                "case_id": "<invalid-json>",
                "ok": false,
                "error": {"category": "invalid_input"},
            });
        }
    };

    let case_id = request
        .get("case_id")
        .and_then(Value::as_str)
        .unwrap_or("<missing-case-id>");
    let operation = request
        .get("operation")
        .and_then(Value::as_str)
        .unwrap_or("");
    let input = match request.get("input") {
        Some(value) if value.is_object() => value,
        _ => {
            return json!({
                "case_id": case_id,
                "ok": false,
                "error": {"category": "invalid_input"},
            });
        }
    };

    match execute(operation, input) {
        Ok(result) => json!({"case_id": case_id, "ok": true, "result": result}),
        Err(error) => json!({
            "case_id": case_id,
            "ok": false,
            "error": {"category": error.category()},
        }),
    }
}

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());

    for line in stdin.lock().lines() {
        let response = match line {
            Ok(line) if line.trim().is_empty() => continue,
            Ok(line) => handle_line(&line),
            Err(error) => {
                eprintln!("failed to read portfolio v1 request: {error}");
                std::process::exit(2);
            }
        };

        if serde_json::to_writer(&mut output, &response).is_err() || writeln!(&mut output).is_err()
        {
            eprintln!("failed to write portfolio v1 response");
            std::process::exit(2);
        }
    }

    if output.flush().is_err() {
        eprintln!("failed to flush portfolio v1 responses");
        std::process::exit(2);
    }
}
